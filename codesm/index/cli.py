"""CLI commands for codebase indexing"""

import asyncio
import typer
from pathlib import Path
from rich.console import Console

from .indexer import ProjectIndexer
from .index_store import IndexStore
from codesm.util.project_id import get_project_id

console = Console()
index_app = typer.Typer(help="Manage codebase index")


@index_app.command("build")
def build_index(
    path: Path = typer.Argument(Path("."), help="Directory to index"),
    force: bool = typer.Option(False, "--force", "-f", help="Force rebuild"),
):
    """Build or rebuild the codebase index"""
    root = path.resolve()
    if not root.exists():
        console.print(f"[red]Path does not exist: {root}[/red]")
        raise typer.Exit(1)
    
    indexer = ProjectIndexer(root)
    console.print(f"[bold]Building index for {root}...[/bold]")
    
    with console.status("Indexing..."):
        asyncio.run(indexer.ensure_index(force=force))
    
    project_id = get_project_id(root)
    store = IndexStore()
    chunks = store.load_chunks(project_id)
    chunk_count = len(chunks) if chunks else 0
    
    console.print(f"[green]✓ Index built successfully[/green]")
    console.print(f"  Chunks indexed: {chunk_count}")


@index_app.command("status")
def index_status(
    path: Path = typer.Argument(Path("."), help="Directory to check"),
):
    """Show index status for a directory"""
    root = path.resolve()
    project_id = get_project_id(root)
    store = IndexStore()
    
    meta = store.load_meta(project_id)
    if not meta:
        console.print(f"[yellow]No index for {root}[/yellow]")
        console.print("Run 'codesm index build' to create one.")
        return
    
    chunks = store.load_chunks(project_id)
    chunk_count = len(chunks) if chunks else 0
    file_count = len(meta.get("file_state", {}))
    
    console.print(f"[bold]Index status for {root}:[/bold]")
    console.print(f"  Project ID: [cyan]{project_id}[/cyan]")
    console.print(f"  Files indexed: {file_count}")
    console.print(f"  Chunks: {chunk_count}")
    console.print(f"  Model: {meta.get('embedding_model', 'unknown')}")
    console.print(f"  Updated: {meta.get('updated_at', 'unknown')}")


@index_app.command("clear")
def clear_index(
    path: Path = typer.Argument(Path("."), help="Directory to clear index for"),
):
    """Clear the index for a directory"""
    root = path.resolve()
    project_id = get_project_id(root)
    store = IndexStore()
    
    from codesm.storage.storage import Storage
    Storage.delete(["index", "project", project_id, "meta"])
    
    cache_path = store.get_cache_path(project_id)
    if cache_path.exists():
        cache_path.unlink()
    
    console.print(f"[green]Cleared index for {root}[/green]")


@index_app.command("search")
def search_index(
    query: str = typer.Argument(..., help="Search query"),
    path: Path = typer.Option(Path("."), "--path", "-p", help="Directory to search"),
    top_k: int = typer.Option(5, "--top", "-k", help="Number of results"),
):
    """Search the codebase index"""
    root = path.resolve()
    indexer = ProjectIndexer(root)
    
    async def do_search():
        await indexer.ensure_index()
        return await indexer.search(query, top_k)
    
    with console.status("Searching..."):
        results = asyncio.run(do_search())
    
    if not results:
        console.print("[yellow]No results found[/yellow]")
        return
    
    console.print(f"[bold]Found {len(results)} results:[/bold]\n")
    for i, result in enumerate(results, 1):
        score = result.get("score", 0)
        file_path = result.get("file", "unknown")
        start_line = result.get("start_line", 0)
        end_line = result.get("end_line", 0)
        content = result.get("content", "")[:200]
        
        console.print(f"[cyan]{i}. {file_path}:{start_line}-{end_line}[/cyan] (score: {score:.3f})")
        console.print(f"   {content}...")
        console.print()
