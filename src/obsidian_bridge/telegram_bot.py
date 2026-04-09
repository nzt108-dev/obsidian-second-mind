"""Telegram Capture Bot for Obsidian Second Mind.

v0.6.0: Capture Gateway — record ideas, links, and decisions from Telegram
directly into the Obsidian vault. No LLM needed — just markdown file operations.

Architecture:
    Bot runs locally on your Mac in polling mode. When you send a message
    from your phone, Telegram servers hold it until the bot picks it up.
    If Mac is off — messages queue up and arrive when bot restarts.

    Phone → Telegram Cloud → Bot (Mac, polling) → ~/SecondMind/inbox/*.md

Usage:
    obsidian-bridge bot          # Start in polling mode
    OBSIDIAN_BRIDGE_TELEGRAM_BOT_TOKEN=xxx obsidian-bridge bot

Behavior:
    - ANY text message → saved to inbox/ as a note
    - Messages with URLs → auto-detected, saved with page title
    - Optional commands: /search, /projects, /status, /help
    - @project prefix → routes to specific project folder
    - Forwarded messages → tagged as 'forwarded'
    - Photos with caption → caption saved as note
"""
import logging
import re
from datetime import date, datetime
from pathlib import Path

import httpx

from obsidian_bridge.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Media Processing (lazy imports — graceful degradation if not installed)
# ---------------------------------------------------------------------------

def _check_whisper() -> bool:
    """Check if Whisper is available for voice transcription."""
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _check_ocr() -> bool:
    """Check if Tesseract OCR is available for image text extraction."""
    try:
        import subprocess
        result = subprocess.run(["tesseract", "--version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


async def _transcribe_voice(file_path: Path) -> str:
    """Transcribe voice message using Whisper (local)."""
    try:
        import whisper
        # Load model lazily (cached after first use)
        if not hasattr(_transcribe_voice, "_model"):
            logger.info("Loading Whisper model (base) — first time may take a moment...")
            _transcribe_voice._model = whisper.load_model("base")
        result = _transcribe_voice._model.transcribe(str(file_path), language=None)
        return result.get("text", "").strip()
    except ImportError:
        return ""
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return ""


async def _extract_text_from_image(file_path: Path) -> str:
    """Extract text from image using Tesseract OCR."""
    try:
        import subprocess
        # tesseract with auto language detection (eng+rus)
        result = subprocess.run(
            ["tesseract", str(file_path), "stdout", "-l", "eng+rus", "--psm", "6"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            text = result.stdout.strip()
            # Filter out noise (tesseract sometimes returns garbage)
            if len(text) > 5:
                return text
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"OCR failed: {e}")
    except Exception as e:
        logger.error(f"OCR error: {e}")
    return ""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")
PROJECT_PATTERN = re.compile(r"^@(\w[\w-]*)\s+")


def _extract_project(text: str, default: str = "") -> tuple[str, str]:
    """Extract @project from text. Returns (project, remaining_text)."""
    match = PROJECT_PATTERN.match(text)
    if match:
        return match.group(1), text[match.end():].strip()
    return default, text


def _extract_urls(text: str) -> list[str]:
    """Extract all URLs from text."""
    return URL_PATTERN.findall(text)


async def _fetch_page_title(url: str) -> str:
    """Fetch page title from URL, return URL domain on failure."""
    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "ObsidianSecondMind/0.6"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            match = re.search(r"<title[^>]*>([^<]+)</title>", resp.text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    except Exception as e:
        logger.warning(f"Failed to fetch title for {url}: {e}")
    # Fallback: return domain
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except Exception:
        return url


def _slugify(text: str, max_length: int = 60) -> str:
    """Convert text to filename-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_length] if slug else "untitled"


def _escape_md(text: str) -> str:
    """Escape special Markdown characters for Telegram MarkdownV1.

    Telegram's Markdown parser is fragile — unmatched _ or * cause errors.
    We use HTML parse_mode instead for safety, but keep this for edge cases.
    """
    for char in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(char, f"\\{char}")
    return text


def _create_note_file(
    vault: Path,
    project: str,
    title: str,
    note_type: str,
    content: str,
    tags: list[str],
) -> Path:
    """Create a markdown note file in the vault.

    Uses the same format as mcp_server.py create_note to stay consistent.
    """
    project_dir = vault / project
    project_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    slug = _slugify(title)
    filename = f"{slug}-{timestamp}.md"
    file_path = project_dir / filename

    # Ensure uniqueness (if 2 notes in same minute)
    counter = 1
    while file_path.exists():
        file_path = project_dir / f"{slug}-{timestamp}-{counter}.md"
        counter += 1

    today = date.today().isoformat()
    tags_yaml = "".join(f'  - "{tag}"\n' for tag in tags)

    fm_content = (
        f"---\n"
        f"project: {project}\n"
        f"type: {note_type}\n"
        f"tags:\n"
        f"{tags_yaml}"
        f"priority: medium\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        f"source: telegram\n"
        f"---\n\n"
        f"# {title}\n\n"
        f"{content}\n"
    )

    file_path.write_text(fm_content, encoding="utf-8")
    logger.info(f"Note created: {file_path.relative_to(vault)}")
    return file_path


def _append_to_log(vault: Path, operation: str, project: str = "", title: str = ""):
    """Append entry to vault log.md."""
    log_path = vault / "log.md"
    if not log_path.exists():
        log_path.write_text(
            "# 📋 Vault Log\n> Chronological record of vault operations.\n\n",
            encoding="utf-8",
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"## [{now}] {operation}"
    if project:
        entry += f" | {project}"
    if title:
        entry += f" | {title}"
    entry += "\n\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


# ---------------------------------------------------------------------------
# Bot Handlers
# ---------------------------------------------------------------------------

class TelegramCapture:
    """Telegram bot for capturing ideas into the Obsidian vault.

    Default behavior: ANY incoming text is saved to inbox/.
    URLs are auto-detected and enriched with page titles.
    Optional slash commands provide search and status.
    """

    def __init__(self, vault_path: Path, bot_token: str, allowed_users: list[int],
                 default_project: str = "inbox"):
        self.vault = vault_path
        self.bot_token = bot_token
        self.allowed_users = set(allowed_users)
        self.default_project = default_project

    def _is_allowed(self, user_id: int) -> bool:
        """Check if user is in whitelist. Empty list = allow all."""
        if not self.allowed_users:
            return True
        return user_id in self.allowed_users

    async def _reply(self, update, text: str):
        """Reply using HTML parse mode (safe from Markdown escape issues)."""
        try:
            await update.message.reply_text(text, parse_mode="HTML")
        except Exception:
            # Fallback to plain text if HTML fails
            import html
            clean = html.unescape(re.sub(r"<[^>]+>", "", text))
            await update.message.reply_text(clean)

    async def handle_start(self, update, context):
        """Handle /start and /help commands."""
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("⛔ Access denied.")
            return

        await self._reply(update,
            "🧠 <b>Obsidian Second Mind — Capture Bot</b>\n\n"
            "Просто отправь любое сообщение — оно сохранится в inbox.\n\n"
            "<b>Авто-детект:</b>\n"
            "• Текст → 💡 заметка\n"
            "• URL → 🔗 ссылка с заголовком страницы\n"
            "• @project текст → 📁 в конкретный проект\n\n"
            "<b>Команды:</b>\n"
            "🔍 /search запрос — поиск по vault\n"
            "📂 /projects — список проектов\n"
            "📊 /status — статус vault\n"
        )

    async def handle_search(self, update, context):
        """Handle /search command — semantic search across vault."""
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("⛔ Access denied.")
            return

        query = update.message.text.replace("/search", "", 1).strip()
        if not query:
            await self._reply(update, "🔍 Используй: <code>/search auth flow</code>")
            return

        try:
            from obsidian_bridge.indexer import VaultIndex

            settings = get_settings()
            idx = VaultIndex(settings)

            if idx.count == 0:
                await self._reply(update,
                    "⚠️ Индекс пуст. Запусти <code>obsidian-bridge index</code> сначала.")
                return

            results = idx.search(query, n_results=3)

            if not results:
                await self._reply(update, "🔍 Ничего не найдено.")
                return

            lines = [f"🔍 <b>Search: {query}</b>\n"]
            for i, r in enumerate(results, 1):
                snippet = r["text"][:200]
                # Remove markup that could break HTML
                snippet = snippet.replace("<", "&lt;").replace(">", "&gt;")
                source = r["source"].replace("<", "&lt;").replace(">", "&gt;")
                lines.append(
                    f"<b>{i}. {source}</b> (score: {r['score']})\n"
                    f"Project: <code>{r['project']}</code> | Type: <code>{r['type']}</code>\n"
                    f"{snippet}...\n"
                )

            await self._reply(update, "\n".join(lines))
        except Exception as e:
            logger.error(f"Search failed: {e}")
            await update.message.reply_text(f"❌ Search error: {e}")

    async def handle_projects(self, update, context):
        """Handle /projects command — list all projects."""
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("⛔ Access denied.")
            return

        from obsidian_bridge.parser import get_projects, get_project_notes

        projects = get_projects(self.vault)
        if not projects:
            await self._reply(update, "📂 Нет проектов в vault.")
            return

        lines = ["📂 <b>Projects</b>\n"]
        for p in projects:
            notes = get_project_notes(self.vault, p)
            types = ", ".join(sorted(set(n.note_type for n in notes)))
            lines.append(f"• <b>{p}</b> — {len(notes)} notes ({types})")

        await self._reply(update, "\n".join(lines))

    async def handle_status(self, update, context):
        """Handle /status command — vault status."""
        if not self._is_allowed(update.effective_user.id):
            await update.message.reply_text("⛔ Access denied.")
            return

        from obsidian_bridge.parser import scan_vault, get_projects

        notes = scan_vault(self.vault)
        projects = get_projects(self.vault)

        # Count inbox items
        inbox_dir = self.vault / "inbox"
        inbox_count = len(list(inbox_dir.glob("*.md"))) if inbox_dir.exists() else 0

        await self._reply(update,
            f"📊 <b>Vault Status</b>\n\n"
            f"📁 Projects: {len(projects)}\n"
            f"📝 Total notes: {len(notes)}\n"
            f"📥 Inbox items: {inbox_count}\n"
            f"📍 Path: <code>{self.vault}</code>"
        )

    async def handle_message(self, update, context):
        """Handle ANY incoming message — the main capture handler.

        Auto-detects content type:
        - Text with URLs → saves as research/link note with page title
        - Text with @project prefix → routes to specific project
        - Plain text → saves as idea/note to inbox
        - Forwarded messages → tagged as 'forwarded'
        """
        if not self._is_allowed(update.effective_user.id):
            return

        text = update.message.text or ""
        caption = update.message.caption or ""
        content = text or caption
        content = content.strip()

        if not content:
            # No text — but check if it's a photo/voice that we can process
            return

        # Check if forwarded (v22+: forward_origin replaces forward_date)
        forward_origin = getattr(update.message, "forward_origin", None)
        is_forwarded = forward_origin is not None
        forward_info = ""
        if is_forwarded:
            # Try to extract sender name from forward_origin
            sender_name = getattr(forward_origin, "sender_user_name", None)
            if not sender_name:
                sender_user = getattr(forward_origin, "sender_user", None)
                if sender_user:
                    sender_name = sender_user.first_name
            if not sender_name:
                sender_name = getattr(forward_origin, "chat", None)
                if sender_name:
                    sender_name = sender_name.title or sender_name.username
            if sender_name:
                forward_info = f"\n> Forwarded from: {sender_name}"

        # Extract optional @project
        project, content = _extract_project(content, self.default_project)

        # Auto-detect URLs
        urls = _extract_urls(content)

        if urls:
            # URL mode → save as research/link
            await self._save_link(update, content, urls, project, is_forwarded, forward_info)
        else:
            # Plain text → save as idea
            await self._save_idea(update, content, project, is_forwarded, forward_info)

    async def _save_idea(self, update, text: str, project: str,
                         is_forwarded: bool, forward_info: str):
        """Save plain text as an idea note."""
        title = text[:80].rstrip(".")
        tags = ["telegram", "inbox"]
        if is_forwarded:
            tags.append("forwarded")

        source_label = "Forwarded" if is_forwarded else "Captured"
        note_content = f"{text}{forward_info}\n\n> 📱 {source_label} via Telegram"

        path = _create_note_file(
            vault=self.vault,
            project=project,
            title=title,
            note_type="note",
            content=note_content,
            tags=tags,
        )

        _append_to_log(self.vault, "telegram_capture", project, title)
        rel = path.relative_to(self.vault)
        await self._reply(update, f"✅ → <code>{rel}</code>")

    async def _save_link(self, update, text: str, urls: list[str], project: str,
                         is_forwarded: bool, forward_info: str):
        """Save text with URLs as a research/link note."""
        # Fetch title for the first URL
        primary_url = urls[0]
        page_title = await _fetch_page_title(primary_url)

        # Build content
        content_parts = []
        for url in urls:
            if url == primary_url:
                content_parts.append(f"**URL**: [{page_title}]({url})")
            else:
                content_parts.append(f"**URL**: {url}")

        # Text without URLs = description
        description = text
        for url in urls:
            description = description.replace(url, "").strip()
        if description:
            content_parts.append(f"\n**Notes**: {description}")

        if forward_info:
            content_parts.append(forward_info)

        source_label = "Forwarded" if is_forwarded else "Captured"
        content_parts.append(f"\n> 🔗 {source_label} via Telegram")

        tags = ["link", "telegram", "research"]
        if is_forwarded:
            tags.append("forwarded")

        title = f"Link: {page_title[:60]}"
        path = _create_note_file(
            vault=self.vault,
            project=project,
            title=title,
            note_type="research",
            content="\n".join(content_parts),
            tags=tags,
        )

        _append_to_log(self.vault, "telegram_link", project, page_title[:60])
        rel = path.relative_to(self.vault)
        await self._reply(update,
            f"🔗 → <code>{rel}</code>\n"
            f"📰 {page_title}"
        )

    async def handle_voice(self, update, context):
        """Handle voice messages — transcribe with Whisper and save."""
        if not self._is_allowed(update.effective_user.id):
            return

        if not _check_whisper():
            await self._reply(update,
                "🎤 Голосовое получено, но Whisper не установлен.\n"
                "Установи: <code>pip install openai-whisper</code>"
            )
            return

        await self._reply(update, "🎤 Транскрибирую...")

        try:
            # Download voice file
            voice = update.message.voice or update.message.audio
            voice_file = await context.bot.get_file(voice.file_id)

            # Save to temp file
            import tempfile
            tmp = Path(tempfile.mkdtemp()) / f"voice_{voice.file_id}.ogg"
            await voice_file.download_to_drive(str(tmp))

            # Transcribe
            text = await _transcribe_voice(tmp)

            # Cleanup
            tmp.unlink(missing_ok=True)
            tmp.parent.rmdir()

            if not text:
                await self._reply(update, "🎤 Не удалось распознать речь.")
                return

            # Save as note
            title = text[:80].rstrip(".")
            path = _create_note_file(
                vault=self.vault,
                project=self.default_project,
                title=title,
                note_type="note",
                content=f"{text}\n\n> 🎤 Voice message, transcribed via Whisper",
                tags=["telegram", "voice", "inbox"],
            )

            _append_to_log(self.vault, "telegram_voice", self.default_project, title)
            rel = path.relative_to(self.vault)
            await self._reply(update,
                f"🎤 → <code>{rel}</code>\n"
                f"📝 {text[:150]}{'...' if len(text) > 150 else ''}"
            )
        except Exception as e:
            logger.error(f"Voice processing failed: {e}")
            await self._reply(update, f"❌ Ошибка обработки голосового: {e}")

    async def handle_photo(self, update, context):
        """Handle photos without caption — OCR text extraction."""
        if not self._is_allowed(update.effective_user.id):
            return

        if not _check_ocr():
            await self._reply(update,
                "📸 Фото получено, но Tesseract OCR не установлен.\n"
                "Установи: <code>brew install tesseract tesseract-lang</code>"
            )
            return

        await self._reply(update, "📸 Извлекаю текст...")

        try:
            # Get the highest resolution photo
            photo = update.message.photo[-1]  # Last = highest res
            photo_file = await context.bot.get_file(photo.file_id)

            # Save to temp file
            import tempfile
            tmp = Path(tempfile.mkdtemp()) / f"photo_{photo.file_id}.jpg"
            await photo_file.download_to_drive(str(tmp))

            # OCR
            text = await _extract_text_from_image(tmp)

            # Cleanup
            tmp.unlink(missing_ok=True)
            tmp.parent.rmdir()

            if not text:
                await self._reply(update, "📸 Текст на изображении не найден.")
                return

            # Save as note
            title = f"Screenshot: {text[:60].rstrip('.')}"
            path = _create_note_file(
                vault=self.vault,
                project=self.default_project,
                title=title,
                note_type="note",
                content=f"{text}\n\n> 📸 Extracted from screenshot via OCR",
                tags=["telegram", "screenshot", "ocr", "inbox"],
            )

            _append_to_log(self.vault, "telegram_ocr", self.default_project, title)
            rel = path.relative_to(self.vault)
            # Show first 200 chars of extracted text
            preview = text[:200].replace("<", "&lt;").replace(">", "&gt;")
            await self._reply(update,
                f"📸 → <code>{rel}</code>\n"
                f"📝 {preview}{'...' if len(text) > 200 else ''}"
            )
        except Exception as e:
            logger.error(f"Photo OCR failed: {e}")
            await self._reply(update, f"❌ Ошибка OCR: {e}")


# ---------------------------------------------------------------------------
# Bot Setup & Runner
# ---------------------------------------------------------------------------

def create_bot(settings=None):
    """Create and configure the Telegram bot application."""
    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    if settings is None:
        settings = get_settings()

    if not settings.telegram_bot_token:
        raise ValueError(
            "Telegram bot token not set. "
            "Set OBSIDIAN_BRIDGE_TELEGRAM_BOT_TOKEN in .env or environment."
        )

    capture = TelegramCapture(
        vault_path=settings.vault_path,
        bot_token=settings.telegram_bot_token,
        allowed_users=settings.telegram_allowed_users,
        default_project=settings.telegram_default_project,
    )

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Command handlers (only utility commands, no /idea or /link needed)
    app.add_handler(CommandHandler("start", capture.handle_start))
    app.add_handler(CommandHandler("help", capture.handle_start))
    app.add_handler(CommandHandler("search", capture.handle_search))
    app.add_handler(CommandHandler("projects", capture.handle_projects))
    app.add_handler(CommandHandler("status", capture.handle_status))

    # Catch-all: ANY text message (with or without command) → inbox
    # This makes slash commands optional — just type anything
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        capture.handle_message,
    ))

    # Photo/video/document with caption → capture the caption
    app.add_handler(MessageHandler(
        filters.CAPTION,
        capture.handle_message,
    ))

    # Voice messages → transcribe with Whisper
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO,
        capture.handle_voice,
    ))

    # Photos without caption → OCR text extraction
    app.add_handler(MessageHandler(
        filters.PHOTO & ~filters.CAPTION,
        capture.handle_photo,
    ))

    logger.info(f"Bot configured. Vault: {settings.vault_path}")
    return app


def run_bot():
    """Start the Telegram bot in polling mode."""
    settings = get_settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("🤖 Starting Obsidian Second Mind — Telegram Capture Bot")
    logger.info(f"   Vault: {settings.vault_path}")
    logger.info(f"   Default project: {settings.telegram_default_project}")
    logger.info(f"   Allowed users: {settings.telegram_allowed_users or 'all'}")
    logger.info(f"   Data: {settings.vault_path / settings.telegram_default_project}/")

    # Ensure inbox dir exists
    inbox = settings.vault_path / settings.telegram_default_project
    inbox.mkdir(parents=True, exist_ok=True)

    app = create_bot(settings)
    app.run_polling(drop_pending_updates=True)


def main():
    """CLI entry point."""
    run_bot()


if __name__ == "__main__":
    main()
