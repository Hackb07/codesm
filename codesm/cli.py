"""CLI entry point for codesm"""

import typer
from pathlib import Path

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
        "anthropic/claude-sonnet-4-20250514",
        "--model", "-m",
        help="Model to use (provider/model)",
    ),
):
    """Start the codesm agent"""
    from codesm.tui.app import CodesmApp
    
    app = CodesmApp(directory=directory, model=model)
    app.run()


@app.command()
def chat(
    message: str = typer.Argument(..., help="Message to send"),
    directory: Path = typer.Option(Path("."), "--dir", "-d"),
    model: str = typer.Option("anthropic/claude-sonnet-4-20250514", "--model", "-m"),
):
    """Send a single message (non-interactive)"""
    import asyncio
    from codesm.agent.agent import Agent
    
    async def run_chat():
        agent = Agent(directory=directory, model=model)
        async for chunk in agent.chat(message):
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


def main():
    app()


if __name__ == "__main__":
    main()
