"""Tests for SessionHooks (hooks.py)."""
import json
import threading
from pathlib import Path

from obsidian_bridge.hooks import SessionHooks, SessionSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_hooks(tmp_path: Path, max_snapshots: int = 50) -> SessionHooks:
    """Create SessionHooks backed by tmp_path vault (no real filesystem access)."""
    return SessionHooks(vault_path=tmp_path, project_base_dirs=[], max_snapshots=max_snapshots)


def _count_archives(hooks: SessionHooks, project: str) -> int:
    """Count timestamped archive files (excluding -latest.json and wakeup-*)."""
    return sum(
        1
        for f in hooks._memory_dir.glob(f"{project}-*.json")
        if not f.name.endswith("-latest.json") and not f.name.startswith("wakeup-")
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSessionHooks:
    def test_save_session_creates_snapshot(self, tmp_path):
        """save_session writes both -latest.json and a timestamped archive."""
        hooks = make_hooks(tmp_path)
        hooks.save_session("myproj", summary="initial save")

        latest = hooks._memory_dir / "myproj-latest.json"
        assert latest.exists(), "-latest.json must be created by save_session"

        # At least one timestamped archive must exist
        archives = list(
            f
            for f in hooks._memory_dir.glob("myproj-*.json")
            if not f.name.endswith("-latest.json")
        )
        assert len(archives) >= 1, "Timestamped archive must be created"

        # Verify content is readable JSON with expected fields
        data = json.loads(latest.read_text())
        assert data["project"] == "myproj"
        assert data["summary"] == "initial save"
        assert "timestamp" in data

    def test_load_session_returns_latest(self, tmp_path):
        """load_last_session returns the most recently saved snapshot."""
        hooks = make_hooks(tmp_path)
        hooks.save_session("myproj", summary="first")
        hooks.save_session("myproj", summary="second")

        loaded = hooks.load_last_session("myproj")

        assert loaded is not None, "load_last_session must not return None after save"
        assert isinstance(loaded, SessionSnapshot)
        assert loaded.project == "myproj"
        assert loaded.summary == "second", "Must return latest (second) snapshot"

    def test_load_session_missing_project(self, tmp_path):
        """load_last_session returns None gracefully when project has no snapshots."""
        hooks = make_hooks(tmp_path)

        result = hooks.load_last_session("nonexistent-project-xyz")

        assert result is None, "Must return None (not raise) for missing project"

    def test_emergency_save_minimal(self, tmp_path):
        """emergency_save creates a snapshot with git_status, no decisions scan."""
        hooks = make_hooks(tmp_path)
        snap = hooks.emergency_save("emergencyproj")

        assert isinstance(snap, SessionSnapshot)
        assert snap.project == "emergencyproj"
        assert "Emergency" in snap.summary or "emergency" in snap.summary.lower()

        # Snapshot JSON must be persisted
        latest = hooks._memory_dir / "emergencyproj-latest.json"
        assert latest.exists(), "emergency_save must write -latest.json"

        data = json.loads(latest.read_text())
        assert data["project"] == "emergencyproj"

    def test_wakeup_cache_updated(self, tmp_path):
        """save_session updates wakeup-cache.json with the project key."""
        hooks = make_hooks(tmp_path)
        hooks.save_session(
            "cacheproj",
            summary="cache test",
            next_steps=["step 1"],
            blockers=["blocker A"],
        )

        cache_path = hooks._memory_dir / "wakeup-cache.json"
        assert cache_path.exists(), "wakeup-cache.json must be created"

        cache = json.loads(cache_path.read_text())
        assert "cacheproj" in cache, "Project key must appear in wakeup cache"
        entry = cache["cacheproj"]
        assert "last_session" in entry
        assert entry["summary"] == "cache test"
        assert "next_steps" in entry

    def test_wakeup_cache_atomic(self, tmp_path):
        """After save_session the .tmp file for wakeup-cache must not remain."""
        hooks = make_hooks(tmp_path)
        hooks.save_session("atomicproj", summary="atomic test")

        cache_path = hooks._memory_dir / "wakeup-cache.json"
        tmp_file = cache_path.with_suffix(".tmp")
        assert not tmp_file.exists(), ".tmp must not remain after atomic cache write"
        assert cache_path.exists(), "wakeup-cache.json must exist"

    def test_prune_keeps_n_recent(self, tmp_path):
        """After N+3 snapshots, only N archives remain (oldest pruned)."""
        max_n = 5
        hooks = make_hooks(tmp_path, max_snapshots=max_n)

        # Create N+3 snapshots; use small sleep to ensure unique timestamps
        for i in range(max_n + 3):
            # Directly call _save_snapshot_json with distinct snapshots to
            # get unique filenames without relying on real-clock sleeps.
            snap = SessionSnapshot(
                timestamp=f"2026-01-{i+1:02d} 10:00",
                project="pruneproj",
                summary=f"snapshot {i}",
            )
            # Manufacture a unique timestamp suffix by temporarily monkeypatching
            # datetime — instead, call _save_snapshot_json directly and override
            # the archive name to guarantee uniqueness across fast test runs.
            ts = f"202601{i+1:02d}_100000_{i:06d}"
            archive_path = hooks._memory_dir / f"pruneproj-{ts}.json"
            archive_path.write_text(
                json.dumps(snap.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            # Also write a -latest.json (as save_session would)
            (hooks._memory_dir / "pruneproj-latest.json").write_text(
                json.dumps(snap.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            # Run prune after each write to simulate successive saves
            hooks._prune_old_snapshots("pruneproj")

        remaining = _count_archives(hooks, "pruneproj")
        assert remaining == max_n, (
            f"_prune_old_snapshots must keep exactly {max_n} archives, got {remaining}"
        )

    def test_concurrent_cache_write_filelock(self, tmp_path):
        """Two parallel save_session calls for different projects must both appear in cache."""
        hooks_a = make_hooks(tmp_path)
        hooks_b = make_hooks(tmp_path)

        errors: list[Exception] = []

        def save_a():
            try:
                for _ in range(3):
                    hooks_a.save_session("proj_alpha", summary="alpha save")
            except Exception as e:
                errors.append(e)

        def save_b():
            try:
                for _ in range(3):
                    hooks_b.save_session("proj_beta", summary="beta save")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=save_a)
        t2 = threading.Thread(target=save_b)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Concurrent cache writes raised errors: {errors}"

        cache_path = hooks_a._memory_dir / "wakeup-cache.json"
        assert cache_path.exists()
        cache = json.loads(cache_path.read_text())

        assert "proj_alpha" in cache, "proj_alpha must be in cache after concurrent writes"
        assert "proj_beta" in cache, "proj_beta must be in cache after concurrent writes"

    def test_load_session_corrupt_json(self, tmp_path):
        """Corrupt -latest.json must not crash — returns None gracefully."""
        hooks = make_hooks(tmp_path)
        latest_path = hooks._memory_dir / "badproj-latest.json"
        latest_path.write_text("{ NOT VALID JSON !!!", encoding="utf-8")

        result = hooks.load_last_session("badproj")
        assert result is None, "Corrupt JSON must return None, not crash"
