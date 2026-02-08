"""Command-line interface for Fizban."""

import json
import logging

import click

from fizban import __version__
from fizban.config import get_config


@click.group()
@click.version_option(version=__version__, prog_name="fizban")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging.")
def cli(verbose: bool) -> None:
    """Fizban - Local documentation knowledge base with MCP server."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@cli.command()
def pull() -> None:
    """Pull latest changes from all configured repos."""
    from fizban.repos import pull_all

    click.echo("Pulling repos...")
    results = pull_all()
    for repo, status in results.items():
        icon = "ok" if status == "ok" else "!!"
        click.echo(f"  [{icon}] {repo}: {status}")


@cli.command()
def rebuild() -> None:
    """Full rebuild of the search index."""
    from fizban.indexer import rebuild_index

    click.echo("Rebuilding index (this may take a while)...")
    stats = rebuild_index()
    click.echo(
        f"Done. Scanned {stats['total_files']} files, indexed {stats['indexed']}."
    )


@cli.command()
def update() -> None:
    """Incremental update of the search index."""
    from fizban.indexer import update_index

    click.echo("Updating index...")
    stats = update_index()
    click.echo(
        f"Done. Scanned {stats['total_files']} files, "
        f"indexed {stats['indexed']} changed, "
        f"removed {stats['removed']} deleted."
    )


@cli.command("serve-mcp")
def serve_mcp() -> None:
    """Start the MCP server (stdio transport)."""
    from fizban.mcp_server import serve

    serve()


@cli.command()
def doctor() -> None:
    """Check system health and configuration."""
    config = get_config()

    click.echo(f"Fizban v{__version__}")
    click.echo(f"  DB path:        {config.db_path}")
    click.echo(f"  DB exists:      {config.db_path.exists()}")
    click.echo(f"  Vector backend: {config.vector_backend}")
    click.echo(f"  Embedding model: {config.embedding_model}")
    click.echo(f"  Chunk size:     {config.chunk_size}")
    click.echo(f"  Chunk overlap:  {config.chunk_overlap}")

    # Check repos
    click.echo("\nRepositories:")
    from pathlib import Path

    for repo in config.repos:
        exists = Path(repo).exists()
        is_git = (Path(repo) / ".git").exists()
        status = (
            "ok" if exists and is_git else ("exists (not git)" if exists else "missing")
        )
        click.echo(f"  [{status}] {repo}")

    # Check vector backend
    click.echo("\nVector backend:")
    try:
        if config.vector_backend == "vec":
            import sqlite_vec  # noqa: F401

            click.echo("  sqlite-vec: available")
        else:
            import sqlite_vss  # noqa: F401

            click.echo("  sqlite-vss: available")
    except ImportError:
        click.echo(f"  {config.vector_backend}: NOT available")

    # Check sentence-transformers
    click.echo("\nEmbeddings:")
    try:
        import sentence_transformers  # noqa: F401

        click.echo("  sentence-transformers: available")
    except ImportError:
        click.echo("  sentence-transformers: NOT available")

    # DB stats
    if config.db_path.exists():
        click.echo("\nDatabase stats:")
        from fizban.db import Database

        db = Database(config)
        try:
            stats = db.stats()
            click.echo(f"  Documents: {stats['documents']}")
            click.echo(f"  Chunks:    {stats['chunks']}")
            click.echo(f"  Images:    {stats['images']}")
            click.echo(
                f"  Repos:     {', '.join(stats['repos']) if stats['repos'] else 'none'}"
            )
        except Exception as e:
            click.echo(f"  Error reading DB: {e}")
        finally:
            db.close()

    # Print MCP registration info
    click.echo("\n--- MCP Registration ---")
    click.echo("Add to .mcp.json (project) or ~/.claude.json (global):")
    click.echo(
        json.dumps(
            {"mcpServers": {"fizban": {"command": "fizban", "args": ["serve-mcp"]}}},
            indent=2,
        )
    )


if __name__ == "__main__":
    cli()
