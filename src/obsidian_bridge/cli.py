"""CLI interface for Obsidian Second Mind."""
import logging
import sys

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
    templates = {
        "prd.md": ("prd", f"# {slug.title()} — Product Requirements\n\n## Overview\n\n## Core Features\n"),
        "architecture.md": ("architecture", f"# {slug.title()} — Architecture\n\n## Layers\n\n## Tech Stack\n"),
        "api-rules.md": ("api", f"# {slug.title()} — API Rules\n\n## Endpoints\n\n## Conventions\n"),
        "ui-guidelines.md": ("guidelines", f"# {slug.title()} — UI Guidelines\n\n## Components\n\n## Patterns\n"),
    }

    for filename, (note_type, content) in templates.items():
        file_path = project_dir / filename
        file_path.write_text(
            f"---\nproject: {slug}\ntype: {note_type}\ntags: []\npriority: medium\n"
            f"created: {today}\nupdated: {today}\n---\n\n{content}",
            encoding="utf-8",
        )

    console.print(f"[green]✅ Project '{slug}' created with 4 template notes.[/]")


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


if __name__ == "__main__":
    cli()
