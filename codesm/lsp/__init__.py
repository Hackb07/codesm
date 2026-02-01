"""LSP client module for diagnostics and code intelligence"""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Literal, Optional

from .client import (
    LSPClient,
    Diagnostic,
    Range,
    Location,
    Symbol,
    Hover,
    CallHierarchyItem,
)
from .servers import SERVERS, ServerConfig, get_server_for_file, get_servers_for_file

logger = logging.getLogger(__name__)

_clients: dict[str, LSPClient] = {}
_root_path: Optional[str] = None


async def init(
    root_path: str,
    servers: Optional[list[str]] = None,
) -> dict[str, bool]:
    """
    Initialize LSP servers for the workspace.
    
    Args:
        root_path: Workspace root path
        servers: List of server keys to start (e.g., ["python", "typescript"]).
                 If None, attempts to start servers based on files in workspace.
    
    Returns:
        Dict mapping server name to success status
    """
    global _clients, _root_path
    _root_path = root_path
    
    if servers is None:
        servers = []
        workspace = Path(root_path)
        
        if list(workspace.rglob("*.py"))[:1]:
            if shutil.which("pylsp"):
                servers.append("python")
            elif shutil.which("pyright-langserver"):
                servers.append("python-pyright")
        
        if list(workspace.rglob("*.ts"))[:1] or list(workspace.rglob("*.js"))[:1]:
            if shutil.which("typescript-language-server"):
                servers.append("typescript")
        
        if list(workspace.rglob("*.rs"))[:1]:
            if shutil.which("rust-analyzer"):
                servers.append("rust")
        
        if list(workspace.rglob("*.go"))[:1]:
            if shutil.which("gopls"):
                servers.append("go")
        
        if list(workspace.rglob("*.vue"))[:1]:
            if shutil.which("vue-language-server"):
                servers.append("vue")
        
        if list(workspace.rglob("*.svelte"))[:1]:
            if shutil.which("svelteserver"):
                servers.append("svelte")
        
        if list(workspace.rglob("*.cpp"))[:1] or list(workspace.rglob("*.c"))[:1]:
            if shutil.which("clangd"):
                servers.append("clangd")
        
        if list(workspace.rglob("*.lua"))[:1]:
            if shutil.which("lua-language-server"):
                servers.append("lua")
        
        if list(workspace.rglob("*.zig"))[:1]:
            if shutil.which("zls"):
                servers.append("zig")
        
        if list(workspace.rglob("*.html"))[:1]:
            if shutil.which("vscode-html-language-server"):
                servers.append("html")
        
        if list(workspace.rglob("*.css"))[:1] or list(workspace.rglob("*.scss"))[:1]:
            if shutil.which("vscode-css-language-server"):
                servers.append("css")
        
        if list(workspace.rglob("*.json"))[:1]:
            if shutil.which("vscode-json-language-server"):
                servers.append("json")
        
        if list(workspace.rglob("*.yaml"))[:1] or list(workspace.rglob("*.yml"))[:1]:
            if shutil.which("yaml-language-server"):
                servers.append("yaml")
        
        if list(workspace.rglob("*.sh"))[:1]:
            if shutil.which("bash-language-server"):
                servers.append("bash")
    
    results = {}
    
    for key in servers:
        if key not in SERVERS:
            logger.warning(f"Unknown LSP server: {key}")
            results[key] = False
            continue
        
        config = SERVERS[key]
        
        executable = config.command[0]
        if not shutil.which(executable):
            logger.warning(f"LSP server executable not found: {executable}")
            results[key] = False
            continue
        
        client = LSPClient(config=config, root_path=root_path)
        
        if await client.start():
            if await client.initialize():
                _clients[key] = client
                results[key] = True
                logger.info(f"Started LSP server: {config.name}")
            else:
                await client.shutdown()
                results[key] = False
                logger.warning(f"Failed to initialize LSP server: {config.name}")
        else:
            results[key] = False
    
    return results


def _get_clients_for_file(path: str) -> list[LSPClient]:
    """Get all active clients that handle the given file."""
    server_keys = get_servers_for_file(path)
    return [_clients[key] for key in server_keys if key in _clients]


def _resolve_path(path: str) -> str:
    """Resolve a path to absolute."""
    file_path = Path(path)
    if not file_path.is_absolute() and _root_path:
        file_path = Path(_root_path) / path
    return str(file_path)


def diagnostics(path: Optional[str] = None) -> list[Diagnostic]:
    """
    Get all diagnostics from connected servers.
    
    Args:
        path: Optional file path to filter diagnostics
    
    Returns:
        List of Diagnostic objects
    """
    all_diags = []
    for client in _clients.values():
        all_diags.extend(client.get_diagnostics(path))
    return all_diags


async def touch_file(
    path: str,
    wait_for_diagnostics: bool = True,
    timeout: float = 5.0,
) -> list[Diagnostic]:
    """
    Notify servers about a file (didOpen) and optionally wait for diagnostics.
    
    Args:
        path: File path to notify about
        wait_for_diagnostics: Whether to wait for diagnostics to arrive
        timeout: Max time to wait for diagnostics in seconds
    
    Returns:
        List of diagnostics for the file
    """
    abs_path = _resolve_path(path)
    clients = _get_clients_for_file(abs_path)
    
    if not clients:
        return []
    
    for client in clients:
        await client.did_open(abs_path)
    
    if wait_for_diagnostics:
        await asyncio.sleep(min(timeout, 2.0))
    
    all_diags = []
    for client in clients:
        all_diags.extend(client.get_diagnostics(abs_path))
    return all_diags


async def goto_definition(path: str, line: int, column: int) -> list[Location]:
    """
    Get definition locations for a symbol at the given position.
    
    Args:
        path: File path
        line: 1-based line number
        column: 1-based column number
    
    Returns:
        List of Location objects
    """
    abs_path = _resolve_path(path)
    clients = _get_clients_for_file(abs_path)
    
    if not clients:
        return []
    
    all_locations = []
    for client in clients:
        locations = await client.definition(abs_path, line, column)
        all_locations.extend(locations)
    
    return all_locations


async def find_references(
    path: str, line: int, column: int, include_declaration: bool = True
) -> list[Location]:
    """
    Find all references to a symbol at the given position.
    
    Args:
        path: File path
        line: 1-based line number
        column: 1-based column number
        include_declaration: Whether to include the declaration in results
    
    Returns:
        List of Location objects
    """
    abs_path = _resolve_path(path)
    clients = _get_clients_for_file(abs_path)
    
    if not clients:
        return []
    
    all_locations = []
    for client in clients:
        locations = await client.references(abs_path, line, column, include_declaration)
        all_locations.extend(locations)
    
    return all_locations


async def hover(path: str, line: int, column: int) -> Optional[Hover]:
    """
    Get hover information for a symbol at the given position.
    
    Args:
        path: File path
        line: 1-based line number
        column: 1-based column number
    
    Returns:
        Hover object or None if no hover info available
    """
    abs_path = _resolve_path(path)
    clients = _get_clients_for_file(abs_path)
    
    for client in clients:
        result = await client.hover(abs_path, line, column)
        if result:
            return result
    
    return None


async def document_symbols(path: str) -> list[Symbol]:
    """
    Get all symbols in a document.
    
    Args:
        path: File path
    
    Returns:
        List of Symbol objects
    """
    abs_path = _resolve_path(path)
    clients = _get_clients_for_file(abs_path)
    
    if not clients:
        return []
    
    all_symbols = []
    for client in clients:
        symbols = await client.document_symbols(abs_path)
        all_symbols.extend(symbols)
    
    return all_symbols


async def workspace_symbols(query: str) -> list[Symbol]:
    """
    Search for symbols across the workspace.
    
    Args:
        query: Search query string
    
    Returns:
        List of Symbol objects
    """
    all_symbols = []
    for client in _clients.values():
        symbols = await client.workspace_symbols(query)
        all_symbols.extend(symbols)
    
    return all_symbols


async def call_hierarchy(
    path: str, line: int, column: int, direction: Literal["incoming", "outgoing"]
) -> list:
    """
    Get call hierarchy for a symbol at the given position.
    
    Args:
        path: File path
        line: 1-based line number
        column: 1-based column number
        direction: "incoming" for callers, "outgoing" for callees
    
    Returns:
        List of call hierarchy items with call info
    """
    abs_path = _resolve_path(path)
    clients = _get_clients_for_file(abs_path)
    
    if not clients:
        return []
    
    all_calls = []
    for client in clients:
        items = await client.prepare_call_hierarchy(abs_path, line, column)
        for item in items:
            if direction == "incoming":
                calls = await client.incoming_calls(item)
            else:
                calls = await client.outgoing_calls(item)
            all_calls.extend(calls)
    
    return all_calls


def status() -> dict[str, dict]:
    """
    Get status of connected servers.
    
    Returns:
        Dict mapping server key to status info
    """
    result = {}
    for key, client in _clients.items():
        result[key] = {
            "name": client.config.name,
            "running": client.process is not None and client.process.returncode is None,
            "initialized": client._initialized,
            "diagnostics_count": len(client.get_diagnostics()),
        }
    return result


async def shutdown() -> None:
    """Shutdown all connected LSP servers."""
    global _clients
    
    tasks = [client.shutdown() for client in _clients.values()]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    _clients.clear()
    logger.info("All LSP servers shut down")


__all__ = [
    # Initialization and lifecycle
    "init",
    "shutdown",
    "status",
    # File operations
    "touch_file",
    "diagnostics",
    # Code intelligence
    "goto_definition",
    "find_references",
    "hover",
    "document_symbols",
    "workspace_symbols",
    "call_hierarchy",
    # Types
    "Diagnostic",
    "Range",
    "Location",
    "Symbol",
    "Hover",
    "CallHierarchyItem",
    # Client and configuration
    "LSPClient",
    "SERVERS",
    "ServerConfig",
    "get_server_for_file",
    "get_servers_for_file",
]
