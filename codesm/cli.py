"""CLI entry point for codesm"""

import typer
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("codesm.log"),
        logging.StreamHandler(),
    ]
)

app = typer.Typer(
    name="codesm",
    help="AI coding agent",
    add_completion=False,
)


@app.command()
def run(
    directory: Path = typer.Argument(
        Path("."),
        help="Directory to run in",
    ),
    model: str = typer.Option(
        None,
        "--model", "-m",
        help="Model to use (provider/model)",
    ),
    session: str = typer.Option(
        None,
        "--session", "-s",
        help="Session ID to load (for continuing previous conversations)",
    ),
):
    """Start the codesm agent"""
    from codesm.tui.app import CodesmApp
    from codesm.auth.credentials import CredentialStore

    # Use preferred model from config if no model specified
    if model is None:
        store = CredentialStore()
        model = store.get_preferred_model() or "anthropic/claude-sonnet-4-20250514"

    app = CodesmApp(directory=directory, model=model, session_id=session)
    app.run()


@app.command()
def chat(
    message: str = typer.Argument(..., help="Message to send"),
    directory: Path = typer.Option(Path("."), "--dir", "-d"),
    model: str = typer.Option(None, "--model", "-m"),
):
    """Send a single message (non-interactive)"""
    import asyncio
    from codesm.agent.agent import Agent
    from codesm.auth.credentials import CredentialStore

    # Use preferred model from config if no model specified
    if model is None:
        store = CredentialStore()
        model = store.get_preferred_model() or "anthropic/claude-sonnet-4-20250514"

    async def run_chat():
        agent = Agent(directory=directory, model=model)
        async for chunk in agent.chat(message):
            # chunk is a StreamChunk object, extract the content
            if hasattr(chunk, 'content'):
                print(chunk.content, end="", flush=True)
            else:
                print(chunk, end="", flush=True)
        print()

    asyncio.run(run_chat())


@app.command()
def serve(
    port: int = typer.Option(4096, "--port", "-p"),
    directory: Path = typer.Option(Path("."), "--dir", "-d"),
):
    """Start HTTP API server"""
    from codesm.server.server import start_server
    start_server(port=port, directory=directory)


# MCP subcommands
mcp_app = typer.Typer(help="MCP (Model Context Protocol) management")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("list")
def mcp_list(
    config: Path = typer.Option(None, "--config", "-c", help="Path to MCP config file"),
):
    """List configured MCP servers"""
    from codesm.mcp import load_mcp_config
    from rich.console import Console
    from rich.table import Table

    console = Console()
    servers = load_mcp_config(config)

    if not servers:
        console.print("[yellow]No MCP servers configured[/yellow]")
        console.print("Create a config file with 'codesm mcp init'")
        return

    table = Table(title="MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Command", style="green")
    table.add_column("Transport")

    for name, server in servers.items():
        cmd = f"{server.command} {' '.join(server.args)}"
        if len(cmd) > 50:
            cmd = cmd[:47] + "..."
        table.add_row(name, cmd, server.transport)

    console.print(table)


@mcp_app.command("test")
def mcp_test(
    server_name: str = typer.Argument(None, help="Server name to test (tests all if omitted)"),
    config: Path = typer.Option(None, "--config", "-c", help="Path to MCP config file"),
):
    """Test connection to MCP servers"""
    import asyncio
    from codesm.mcp import load_mcp_config, MCPManager
    from rich.console import Console

    console = Console()
    servers = load_mcp_config(config)

    if not servers:
        console.print("[red]No MCP servers configured[/red]")
        return

    async def test_servers():
        manager = MCPManager()
        
        for name, server_config in servers.items():
            if server_name and name != server_name:
                continue
            manager.add_server(server_config)

        with console.status("Connecting to MCP servers..."):
            results = await manager.connect_all()

        for name, success in results.items():
            if success:
                client = manager._clients.get(name)
                tools = len(client.tools) if client else 0
                resources = len(client.resources) if client else 0
                console.print(f"[green]✓[/green] {name}: {tools} tools, {resources} resources")
            else:
                console.print(f"[red]✗[/red] {name}: connection failed")

        # List discovered tools
        tools = manager.list_all_tools()
        if tools:
            console.print(f"\n[bold]Discovered {len(tools)} tools:[/bold]")
            for tool in tools:
                console.print(f"  • {tool['server']}/{tool['name']}: {tool['description'][:60]}...")

        await manager.disconnect_all()

    asyncio.run(test_servers())


@mcp_app.command("init")
def mcp_init(
    path: Path = typer.Argument(Path("mcp-servers.json"), help="Path to create config file"),
):
    """Create an example MCP configuration file"""
    from codesm.mcp import create_example_config
    from rich.console import Console

    console = Console()
    
    if path.exists():
        if not typer.confirm(f"{path} already exists. Overwrite?"):
            raise typer.Abort()

    create_example_config(path)
    console.print(f"[green]Created example MCP config at {path}[/green]")
    console.print("Edit the file to configure your MCP servers.")


def main():
    app()


if __name__ == "__main__":
    main()
