"""CLI interface for Obsidian Second Mind."""
import logging

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from obsidian_bridge.config import get_settings

console = Console()


@click.group()
@click.option("--vault", type=click.Path(exists=True), help="Path to Obsidian vault")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
@click.pass_context
def cli(ctx, vault, verbose):
    """🧠 Obsidian Second Mind — AI Bridge for your knowledge base."""
    ctx.ensure_object(dict)
    settings = get_settings()
    if vault:
        settings.vault_path = vault
    ctx.obj["settings"] = settings

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


@cli.command()
@click.pass_context
def serve(ctx):
    """Start the MCP server (stdio mode for IDE integration)."""
    # MCP uses stdio for JSON-RPC — all human-readable output MUST go to stderr
    err_console = Console(stderr=True)
    err_console.print("[bold green]Starting MCP server...[/]")
    err_console.print(f"Vault: {ctx.obj['settings'].vault_path}")

    from obsidian_bridge.mcp_server import main
    main()


@cli.command()
@click.pass_context
def index(ctx):
    """Build or rebuild the vector search index."""
    settings = ctx.obj["settings"]
    console.print(f"[bold]Indexing vault:[/] {settings.vault_path}")

    from obsidian_bridge.parser import scan_vault
    from obsidian_bridge.indexer import VaultIndex

    notes = scan_vault(settings.vault_path)
    console.print(f"Found [cyan]{len(notes)}[/] notes")

    idx = VaultIndex(settings)
    idx.clear()
    stats = idx.index_notes(notes)

    console.print(Panel(
        f"✅ Index built!\n"
        f"Notes indexed: [green]{stats['added']}[/]\n"
        f"Total chunks: [green]{stats['total_chunks']}[/]",
        title="Index Stats",
        border_style="green",
    ))


@cli.command()
@click.argument("query")
@click.option("--project", "-p", help="Filter by project")
@click.option("--limit", "-n", default=5, help="Number of results")
@click.pass_context
def search(ctx, query, project, limit):
    """Semantic search across the vault."""
    settings = ctx.obj["settings"]

    from obsidian_bridge.indexer import VaultIndex

    idx = VaultIndex(settings)
    if idx.count == 0:
        console.print("[yellow]Index is empty. Run 'obsidian-bridge index' first.[/]")
        return

    results = idx.search(query, n_results=limit, project=project)

    if not results:
        console.print("[yellow]No results found.[/]")
        return

    for i, r in enumerate(results, 1):
        console.print(Panel(
            f"[dim]{r['source']}[/]\n"
            f"Project: [cyan]{r['project']}[/] | Type: [magenta]{r['type']}[/]\n\n"
            f"{r['text'][:300]}{'...' if len(r['text']) > 300 else ''}",
            title=f"Result {i} (score: {r['score']})",
            border_style="blue",
        ))


@cli.command()
@click.pass_context
def watch(ctx):
    """Start file watcher daemon for auto-indexing."""
    settings = ctx.obj["settings"]

    from obsidian_bridge.indexer import VaultIndex
    from obsidian_bridge.watcher import start_watcher

    idx = VaultIndex(settings)
    console.print(f"[bold green]👁️  Watching:[/] {settings.vault_path}")
    console.print("Press Ctrl+C to stop.")

    observer = start_watcher(settings, idx)
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        console.print("\n[yellow]Watcher stopped.[/]")


@cli.command("list-projects")
@click.pass_context
def list_projects(ctx):
    """List all projects in the vault."""
    settings = ctx.obj["settings"]

    from obsidian_bridge.parser import get_projects, get_project_notes

    projects = get_projects(settings.vault_path)

    table = Table(title="Projects in Vault")
    table.add_column("Project", style="cyan")
    table.add_column("Notes", justify="right")
    table.add_column("Types")

    for p in projects:
        notes = get_project_notes(settings.vault_path, p)
        types = ", ".join(sorted(set(n.note_type for n in notes)))
        table.add_row(p, str(len(notes)), types)

    console.print(table)


@cli.command("add-project")
@click.argument("slug")
@click.pass_context
def add_project(ctx, slug):
    """Create a new project structure in the vault."""
    settings = ctx.obj["settings"]
    project_dir = settings.vault_path / slug

    if project_dir.exists():
        console.print(f"[yellow]Project '{slug}' already exists.[/]")
        return

    project_dir.mkdir(parents=True)
    (project_dir / "decisions").mkdir()

    from datetime import date
    today = date.today().isoformat()

    # Create default files
    title = slug.title()
    templates = {
        "prd.md": (
            "prd",
            f"# {title} — Product Requirements\n\n## Overview\n\n## Core Features\n",
        ),
        "architecture.md": (
            "architecture",
            f"# {title} — Architecture\n\n## Layers\n\n## Tech Stack\n",
        ),
        "api-rules.md": (
            "api",
            f"# {title} — API Rules\n\n## Endpoints\n\n## Conventions\n",
        ),
        "ui-guidelines.md": (
            "guidelines",
            f"# {title} — UI Guidelines\n\n## Components\n\n## Patterns\n",
        ),
    }

    for filename, (note_type, content) in templates.items():
        file_path = project_dir / filename
        file_path.write_text(
            f"---\nproject: {slug}\ntype: {note_type}\ntags: []\npriority: medium\n"
            f"created: {today}\nupdated: {today}\n---\n\n{content}",
            encoding="utf-8",
        )

    console.print(f"[green]✅ Project '{slug}' created with 4 template notes.[/]")


@cli.command("process-inbox")
@click.option("--apply", "do_apply", is_flag=True,
              help="Actually route & remove originals (default: dry-run preview)")
@click.option("--limit", "-n", default=0, help="Max files to process (0 = all)")
@click.pass_context
def process_inbox(ctx, do_apply, limit):
    """Sort accumulated inbox/ notes into projects via the rule-based router.

    Dry-run by default — shows where each note WOULD go. Pass --apply to
    cascade-ingest matched notes into their project and delete the inbox
    original. Unmatched notes stay in inbox/.
    """
    settings = ctx.obj["settings"]
    vault = settings.vault_path

    from obsidian_bridge.parser import get_projects, parse_note
    from obsidian_bridge.inbox_router import classify
    from obsidian_bridge.ingest import IngestPipeline, IngestSource

    inbox_dir = vault / "inbox"
    if not inbox_dir.exists():
        console.print("[yellow]No inbox/ directory.[/]")
        return

    known = get_projects(vault)
    index = None
    if do_apply:
        try:
            from obsidian_bridge.indexer import VaultIndex
            index = VaultIndex(settings)
        except Exception as e:
            console.print(f"[yellow]Index unavailable: {e}[/]")
    pipeline = IngestPipeline(vault_path=vault, index=index)

    table = Table(title="Inbox routing" + ("" if do_apply else " (dry-run)"))
    table.add_column("File", style="dim", overflow="fold")
    table.add_column("→ Project", style="cyan")
    table.add_column("Reason")

    routed = stayed = 0
    files = sorted(inbox_dir.glob("*.md"))
    for md in files:
        # Skip system / generated files.
        if md.name.startswith("github-radar-") or md.name.startswith("_"):
            continue
        note = parse_note(md, vault)
        if not note:
            continue
        decision = classify(note.content, title=note.title, known_projects=known)
        if decision.project == "inbox":
            stayed += 1
            continue

        marker = " 🆕" if decision.is_new_project else ""
        table.add_row(md.name, decision.project + marker, decision.reason)
        routed += 1

        if do_apply:
            source = IngestSource(
                content=note.content,
                source_type="note",
                project=decision.project,
                title=note.title,
                tags=["telegram", "inbox", "routed"],
            )
            pipeline.ingest(source)
            md.unlink()  # remove inbox original after successful ingest

        if limit and routed >= limit:
            break

    console.print(table)
    verb = "Routed" if do_apply else "Would route"
    console.print(f"[green]{verb}: {routed}[/] | [dim]Stayed in inbox: {stayed}[/]")
    if not do_apply and routed:
        console.print("[yellow]Dry-run. Re-run with --apply to move them.[/]")


@cli.command()
@click.pass_context
def status(ctx):
    """Show vault and index status."""
    settings = ctx.obj["settings"]

    from obsidian_bridge.parser import scan_vault
    from obsidian_bridge.indexer import VaultIndex

    notes = scan_vault(settings.vault_path)
    idx = VaultIndex(settings)
    stats = idx.get_stats()

    console.print(Panel(
        f"Vault path: [cyan]{settings.vault_path}[/]\n"
        f"Total notes: [green]{len(notes)}[/]\n"
        f"Indexed chunks: [green]{stats['total_chunks']}[/]\n"
        f"Indexed notes: [green]{stats['total_notes']}[/]\n"
        f"Projects: [cyan]{', '.join(stats['projects']) or 'none'}[/]\n"
        f"Types: [magenta]{', '.join(stats['types']) or 'none'}[/]",
        title="🧠 Obsidian Second Mind — Status",
        border_style="blue",
    ))


@cli.command()
@click.option("--port", "-p", default=9109, help="Server port (default: 9109)")
@click.option("--no-open", is_flag=True, help="Don't auto-open browser")
@click.pass_context
def dashboard(ctx, port, no_open):
    """🚀 Launch Mission Control Dashboard in browser."""
    console.print("[bold cyan]🚀 Launching Mission Control Dashboard...[/]")

    from obsidian_bridge.dashboard_server import run_dashboard
    run_dashboard(port=port, open_browser=not no_open)


@cli.command()
@click.pass_context
def bot(ctx):
    """🤖 Start the Telegram Capture Bot (polling mode)."""
    console.print("[bold cyan]🤖 Starting Telegram Capture Bot...[/]")
    console.print(f"Vault: {ctx.obj['settings'].vault_path}")

    try:
        from obsidian_bridge.telegram_bot import run_bot
        run_bot()
    except ValueError as e:
        console.print(f"[red]❌ {e}[/]")
        console.print("\n[yellow]Set your bot token:[/]")
        console.print("  export OBSIDIAN_BRIDGE_TELEGRAM_BOT_TOKEN=your-token-here")
        console.print("  # or add to .env file")


@cli.command()
@click.argument("text")
@click.option("--project", "-p", default="inbox", help="Target project (default: inbox)")
@click.option("--title", "-t", default="", help="Note title")
@click.option("--type", "source_type", default="text", type=click.Choice(["text", "url", "note"]))
@click.pass_context
def ingest(ctx, text, project, title, source_type):
    """📥 Cascade ingest — one source → N wiki updates."""
    from obsidian_bridge.ingest import IngestPipeline, IngestSource

    settings = ctx.obj["settings"]
    vault = settings.vault_path

    console.print(f"[bold cyan]📥 Cascade Ingest → {project}[/]")

    try:
        from obsidian_bridge.indexer import VaultIndex
        index = VaultIndex(settings)
    except Exception:
        index = None
        console.print("[yellow]⚠️ Index unavailable, skipping semantic search step[/]")

    source = IngestSource(
        content=text,
        source_type=source_type,
        project=project,
        title=title,
    )

    pipeline = IngestPipeline(vault_path=vault, index=index)
    report = pipeline.ingest(source)

    console.print(f"[green]✅ Done! {len(report.actions)} actions, "
                   f"{len(report.entities_found)} entities, "
                   f"{report.cross_references_added} cross-refs[/]")
    for a in report.actions:
        icon = {"created": "✅", "updated": "📝", "cross-referenced": "🔗"}.get(a.action, "•")
        console.print(f"  {icon} {a.action}: {a.path}")


@cli.command()
@click.option("--category", "-c", default="all", type=click.Choice(["mcp", "ai", "devtools", "all"]))
@click.option("--notify/--no-notify", default=True, help="Send Telegram alert")
@click.pass_context
def radar(ctx, category, notify):
    """📡 Auto Radar — scan + diff + notify."""
    import asyncio
    from obsidian_bridge.auto_radar import AutoRadar, notify_telegram

    settings = ctx.obj["settings"]
    vault = settings.vault_path

    console.print(f"[bold cyan]📡 Auto Radar Scan ({category})...[/]")

    auto = AutoRadar(vault)
    diff = asyncio.run(auto.run_scan(category))

    console.print("[green]✅ Scan complete![/]")
    console.print(f"  Current: {diff.total_current} tools")
    console.print(f"  New high: {len(diff.new_high_relevance)}")
    console.print(f"  New medium: {len(diff.new_medium_relevance)}")

    if notify and diff.has_important_changes:
        if settings.telegram_bot_token and settings.telegram_allowed_users:
            sent = asyncio.run(notify_telegram(
                diff=diff,
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_allowed_users[0],
            ))
            if sent:
                console.print("[green]📱 Telegram alert sent![/]")


@cli.command()
@click.argument("project")
@click.option("--summary", "-s", default="", help="Session summary")
@click.option("--next", "next_steps", multiple=True, help="Next steps (repeat for multiple)")
@click.option("--blocker", "blockers", multiple=True, help="Blockers (repeat for multiple)")
@click.pass_context
def save(ctx, project, summary, next_steps, blockers):
    """💾 Save current session context to vault (Agent Memory)."""
    from obsidian_bridge.hooks import SessionHooks

    settings = ctx.obj["settings"]
    hooks = SessionHooks(settings.vault_path, settings.project_base_dirs)

    console.print(f"[bold cyan]💾 Saving session for {project}...[/]")

    snapshot = hooks.save_session(
        project=project,
        summary=summary,
        next_steps=list(next_steps),
        blockers=list(blockers),
    )

    console.print(f"[green]✅ Session saved at {snapshot.timestamp}[/]")
    if snapshot.recent_commits:
        console.print(f"  Commits: {len(snapshot.recent_commits)}")
    if snapshot.uncommitted_changes:
        console.print(f"  [yellow]⚠️ Uncommitted: {len(snapshot.uncommitted_changes)} files[/]")
    if snapshot.next_steps:
        console.print("  Next steps:")
        for s in snapshot.next_steps:
            console.print(f"    → {s}")


@cli.command()
@click.option("--restore", default=None, metavar="DATE",
              help="Restore vault from backup (YYYY-MM-DD)")
@click.option("--dry-run", is_flag=True,
              help="Show what would be backed up without uploading")
@click.option("--remote", default=None,
              help="rclone remote name (overrides config)")
@click.pass_context
def backup(ctx, restore, dry_run, remote):
    """Encrypted cloud backup of the vault via rclone crypt."""
    from obsidian_bridge.backup import BackupConfig, BackupManager

    settings = ctx.obj["settings"]

    cfg = BackupConfig(
        rclone_remote=remote or settings.backup_rclone_remote,
        backup_dir=settings.backup_dir,
        keep_daily=settings.backup_keep_daily,
    )
    mgr = BackupManager(vault_path=settings.vault_path, config=cfg)

    # --- RESTORE mode ---
    if restore:
        console.print(f"[bold yellow]🔄 Restoring vault from backup: {restore}[/]")
        try:
            vault = mgr.restore(restore)
            console.print(f"[green]✅ Vault restored to {vault}[/]")
            console.print("[cyan]Run:[/] obsidian-bridge index")
        except (RuntimeError, FileNotFoundError, ValueError) as exc:
            console.print(f"[red]❌ Restore failed: {exc}[/]")
        return

    # --- DRY-RUN mode ---
    if dry_run:
        console.print("[bold cyan]🔍 Dry run — listing archive contents...[/]")
        import tempfile
        from pathlib import Path as _Path
        try:
            mgr.check_rclone()
        except RuntimeError as exc:
            console.print(f"[red]❌ {exc}[/]")
            return
        with tempfile.TemporaryDirectory(prefix="obsidian-dryrun-") as tmp:
            try:
                archive = mgr.create_archive(_Path(tmp))
                members = mgr.list_archive_contents(archive)
                size_kb = archive.stat().st_size / 1024
                console.print(
                    f"[green]Archive:[/] {archive.name}  "
                    f"([bold]{size_kb:.1f} KB[/])"
                )
                console.print(f"[cyan]{len(members)} files would be uploaded.[/]")
                for m in members[:30]:
                    console.print(f"  {m}")
                if len(members) > 30:
                    console.print(f"  ... and {len(members) - 30} more")
            except FileNotFoundError as exc:
                console.print(f"[red]❌ {exc}[/]")
        return

    # --- NORMAL backup mode ---
    console.print("[bold cyan]☁️  Starting vault backup...[/]")
    console.print(f"Vault: {settings.vault_path}")
    console.print(f"Remote: {cfg.rclone_remote or '(not set)'}")

    result = mgr.backup()

    if result["success"]:
        console.print(Panel(
            f"✅ Backup complete!\n"
            f"Archive size: [green]{result['archive_size_kb']} KB[/]\n"
            f"Remote: [cyan]{result['remote_path']}[/]\n"
            f"Local cache: [dim]{result['local_cache']}[/]",
            title="Backup",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"❌ Backup failed\n"
            f"Local cache: [yellow]{result.get('local_cache') or 'none'}[/]\n"
            f"Error: [red]{result.get('error')}[/]",
            title="Backup",
            border_style="red",
        ))


@cli.command("emergency-save")
@click.argument("project")
@click.pass_context
def emergency_save(ctx, project):
    """⚠️ Fast emergency save — minimal context dump before session loss."""
    from obsidian_bridge.hooks import SessionHooks

    settings = ctx.obj["settings"]
    hooks = SessionHooks(settings.vault_path, settings.project_base_dirs)

    console.print(f"[bold yellow]⚠️ Emergency save for {project}...[/]")

    snapshot = hooks.emergency_save(project)

    console.print(f"[green]✅ Emergency snapshot saved at {snapshot.timestamp}[/]")
    if snapshot.uncommitted_changes:
        console.print(f"  [yellow]Uncommitted: {len(snapshot.uncommitted_changes)} files[/]")


if __name__ == "__main__":
    cli()
