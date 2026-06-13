"""Encrypted cloud backup of the Obsidian vault via rclone crypt.

Flow:
    tar czf → secondmind-YYYY-MM-DD.tar.gz (~600KB–1MB)
        → rclone copy to crypt-remote (gdrive-crypt:obsidian-backups/)
        → rotation: rclone deletes archives older than N days
        → local cache: keep last 3 copies in ~/.obsidian-bridge/backups/

Security: fail-closed — if rclone_remote is empty the backup REFUSES to start,
so vault mnemonics never reach cloud in plaintext.
"""
import logging
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# Patterns excluded from the archive (relative to vault root)
_EXCLUDE_PATTERNS = [
    "*.lock",
    "*.tmp",
    "__pycache__",
    "*.pyc",
]

# The ChromaDB index lives OUTSIDE the vault (~/.obsidian-bridge/chroma),
# so it is never picked up by tarring the vault directory itself.


@dataclass
class BackupConfig:
    """Configuration for backup operations."""

    rclone_remote: str = ""
    backup_dir: str = "obsidian-backups"
    keep_daily: int = 7
    keep_weekly: int = 4
    local_cache_dir: Path = field(
        default_factory=lambda: Path.home() / ".obsidian-bridge" / "backups"
    )


class BackupManager:
    """Orchestrates encrypted cloud backup of the Obsidian vault."""

    def __init__(self, vault_path: Path, config: BackupConfig) -> None:
        self.vault_path = Path(vault_path).expanduser()
        self.config = config

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check_rclone(self) -> bool:
        """Return True if rclone binary is on PATH and remote is configured.

        Raises RuntimeError (fail-closed) if rclone_remote is empty so that
        vault mnemonics never reach the cloud unencrypted.
        """
        if not self.config.rclone_remote:
            raise RuntimeError(
                "rclone remote not configured. "
                "Set OBSIDIAN_BRIDGE_BACKUP_RCLONE_REMOTE to your crypt-remote name "
                "(e.g. 'gdrive-crypt:'). "
                "Setup guide: run `rclone config` and create a crypt remote on top of "
                "Google Drive. See README section 'Backup & Restore'."
            )

        if shutil.which("rclone") is None:
            raise RuntimeError(
                "rclone not found. Install it: brew install rclone"
            )

        return True

    def check_remote_configured(self) -> bool:
        """Check that rclone_remote actually appears in `rclone listremotes`."""
        result = subprocess.run(
            ["rclone", "listremotes"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        remotes = result.stdout.strip().splitlines()
        # Normalise: strip trailing colon for comparison
        remote_name = self.config.rclone_remote.rstrip(":")
        for r in remotes:
            if r.rstrip(":") == remote_name:
                return True
        raise RuntimeError(
            f"rclone remote '{self.config.rclone_remote}' not found in `rclone listremotes`. "
            f"Available remotes: {remotes or ['(none)']}. "
            "Run `rclone config` to configure a crypt remote."
        )

    # ------------------------------------------------------------------
    # Archive
    # ------------------------------------------------------------------

    def _should_exclude(self, tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
        """Filter callback for tarfile.add — returns None to exclude."""
        name = Path(tarinfo.name).name
        parts = Path(tarinfo.name).parts

        # Exclude by pattern
        for pattern in ["*.lock", "*.tmp"]:
            ext = pattern.lstrip("*")
            if name.endswith(ext):
                return None

        # Exclude __pycache__ directories and .pyc files
        if name == "__pycache__" or name.endswith(".pyc"):
            return None

        # Safety: exclude .obsidian-bridge if somehow inside vault
        if ".obsidian-bridge" in parts:
            return None

        return tarinfo

    def create_archive(self, tmp_dir: Path) -> Path:
        """Create a tar.gz snapshot of the vault into tmp_dir.

        Returns the path to the created archive.
        Raises FileNotFoundError if vault does not exist or is empty.
        """
        if not self.vault_path.exists():
            raise FileNotFoundError(
                f"Vault path does not exist: {self.vault_path}"
            )

        md_files = list(self.vault_path.rglob("*.md"))
        if not md_files:
            raise FileNotFoundError(
                f"Vault is empty (no .md files found): {self.vault_path}"
            )

        today = date.today().isoformat()
        archive_name = f"secondmind-{today}.tar.gz"
        archive_path = tmp_dir / archive_name

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(
                str(self.vault_path),
                arcname="SecondMind",
                filter=self._should_exclude,
            )

        logger.info("Archive created: %s (%.1f KB)", archive_path,
                    archive_path.stat().st_size / 1024)
        return archive_path

    def list_archive_contents(self, archive_path: Path) -> list[str]:
        """Return list of member paths inside the archive (for --dry-run)."""
        with tarfile.open(archive_path, "r:gz") as tar:
            return [m.name for m in tar.getmembers()]

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, archive_path: Path) -> bool:
        """Copy archive to rclone remote. Returns True on success."""
        remote_dest = f"{self.config.rclone_remote.rstrip(':')}:{self.config.backup_dir}/"
        try:
            result = subprocess.run(
                ["rclone", "copy", str(archive_path), remote_dest, "--progress"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.error("rclone copy failed: %s", result.stderr)
                return False
            logger.info("Uploaded to %s%s", remote_dest, archive_path.name)
            return True
        except subprocess.TimeoutExpired:
            logger.error("rclone upload timed out after 300s")
            return False
        except OSError as exc:
            logger.error("rclone upload error: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------

    def rotate_remote(self) -> None:
        """Delete remote archives older than keep_daily days."""
        remote_path = (
            f"{self.config.rclone_remote.rstrip(':')}:{self.config.backup_dir}/"
        )
        min_age = f"{self.config.keep_daily}d"
        try:
            result = subprocess.run(
                ["rclone", "delete", remote_path, "--min-age", min_age],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                logger.warning("rclone rotate warning: %s", result.stderr)
            else:
                logger.info("Rotation done — removed archives older than %s", min_age)
        except OSError as exc:
            logger.warning("rclone rotate error (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Local cache
    # ------------------------------------------------------------------

    def save_local_cache(self, archive_path: Path) -> None:
        """Copy archive to local cache, keeping only the last 3 copies."""
        cache_dir = self.config.local_cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

        dest = cache_dir / archive_path.name
        shutil.copy2(str(archive_path), str(dest))
        logger.info("Saved local cache: %s", dest)

        # Keep only last 3
        cached = sorted(cache_dir.glob("secondmind-*.tar.gz"))
        for old in cached[:-3]:
            old.unlink()
            logger.debug("Removed old local cache: %s", old)

    # ------------------------------------------------------------------
    # Full backup cycle
    # ------------------------------------------------------------------

    def backup(self) -> dict:
        """Run the full backup cycle.

        Returns dict with keys: success (bool), archive_size_kb (float),
        remote_path (str), local_cache (str), error (str|None).
        """
        result: dict = {
            "success": False,
            "archive_size_kb": 0.0,
            "remote_path": "",
            "local_cache": "",
            "error": None,
        }

        # --- checks (fail-closed) ---
        try:
            self.check_rclone()
            self.check_remote_configured()
        except RuntimeError as exc:
            result["error"] = str(exc)
            logger.error("Backup aborted: %s", exc)
            return result

        with tempfile.TemporaryDirectory(prefix="obsidian-backup-") as tmp_str:
            tmp_dir = Path(tmp_str)

            # --- create archive ---
            try:
                archive_path = self.create_archive(tmp_dir)
            except FileNotFoundError as exc:
                result["error"] = str(exc)
                logger.error("Backup aborted: %s", exc)
                return result

            size_kb = archive_path.stat().st_size / 1024
            result["archive_size_kb"] = round(size_kb, 1)

            # --- always save local cache first (network may fail) ---
            try:
                self.save_local_cache(archive_path)
                result["local_cache"] = str(
                    self.config.local_cache_dir / archive_path.name
                )
            except OSError as exc:
                logger.warning("Local cache save failed: %s", exc)

            # --- upload ---
            remote_dest = (
                f"{self.config.rclone_remote.rstrip(':')}:"
                f"{self.config.backup_dir}/{archive_path.name}"
            )
            uploaded = self.upload(archive_path)
            if uploaded:
                result["success"] = True
                result["remote_path"] = remote_dest
                # --- rotate old remote archives ---
                self.rotate_remote()
            else:
                result["error"] = (
                    "Upload failed — archive saved locally at "
                    + result["local_cache"]
                    + ". Will retry on next run."
                )
                logger.warning(result["error"])

        return result

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore(self, date_str: str) -> Path:
        """Download, decrypt and unpack a backup for the given date (YYYY-MM-DD).

        Returns the vault path after restoration.
        Prints a reminder to run `obsidian-bridge index` afterwards.
        """
        # validate date format
        try:
            date.fromisoformat(date_str)
        except ValueError as exc:
            raise ValueError(
                f"Invalid date format '{date_str}'. Use YYYY-MM-DD."
            ) from exc

        # fail-closed checks
        self.check_rclone()
        self.check_remote_configured()

        archive_name = f"secondmind-{date_str}.tar.gz"
        remote_src = (
            f"{self.config.rclone_remote.rstrip(':')}:"
            f"{self.config.backup_dir}/{archive_name}"
        )

        with tempfile.TemporaryDirectory(prefix="obsidian-restore-") as tmp_str:
            tmp_dir = Path(tmp_str)

            logger.info("Downloading %s ...", remote_src)
            result = subprocess.run(
                ["rclone", "copy", remote_src, str(tmp_dir), "--progress"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"rclone download failed: {result.stderr.strip()}"
                )

            archive_path = tmp_dir / archive_name
            if not archive_path.exists():
                raise FileNotFoundError(
                    f"Archive not found on remote: {remote_src}"
                )

            # Confirm before overwriting vault
            print(
                f"\n⚠️  This will OVERWRITE {self.vault_path} with the backup from {date_str}.\n"
                "Type 'yes' to confirm: ",
                end="",
                flush=True,
            )
            answer = input()
            if answer.strip().lower() != "yes":
                raise RuntimeError("Restore cancelled by user.")

            logger.info("Extracting %s → %s", archive_path, self.vault_path)
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(str(self.vault_path.parent))  # extracts SecondMind/

        print(
            "\n✅ Restore complete!\n"
            "IMPORTANT: Run the following to rebuild the search index:\n"
            "  obsidian-bridge index\n"
        )
        logger.info("Restore done. Run: obsidian-bridge index")
        return self.vault_path
