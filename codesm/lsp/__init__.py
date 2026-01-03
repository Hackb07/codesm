"""LSP client module for diagnostics and code intelligence"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .client import LSPClient, Diagnostic
from .servers import SERVERS, ServerConfig, get_server_for_file

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
    import shutil
    from pathlib import Path
    
    global _clients, _root_path
    _root_path = root_path
    
    # Detect which servers to start based on file types in workspace
    if servers is None:
        servers = []
        workspace = Path(root_path)
        
        # Check for Python files
        if list(workspace.rglob("*.py"))[:1]:
            if shutil.which("pylsp"):
                servers.append("python")
            elif shutil.which("pyright-langserver"):
                servers.append("python-pyright")
        
        # Check for TypeScript/JavaScript files
        if list(workspace.rglob("*.ts"))[:1] or list(workspace.rglob("*.js"))[:1]:
            if shutil.which("typescript-language-server"):
                servers.append("typescript")
        
        # Check for Rust files
        if list(workspace.rglob("*.rs"))[:1]:
            if shutil.which("rust-analyzer"):
                servers.append("rust")
        
        # Check for Go files
        if list(workspace.rglob("*.go"))[:1]:
            if shutil.which("gopls"):
                servers.append("go")
    
    results = {}
    
    for key in servers:
        if key not in SERVERS:
            logger.warning(f"Unknown LSP server: {key}")
            results[key] = False
            continue
        
        config = SERVERS[key]
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
    file_path = Path(path)
    if not file_path.is_absolute() and _root_path:
        file_path = Path(_root_path) / path
    
    abs_path = str(file_path)
    server_key = get_server_for_file(abs_path)
    
    if server_key and server_key in _clients:
        client = _clients[server_key]
        await client.did_open(abs_path)
        
        if wait_for_diagnostics:
            await asyncio.sleep(min(timeout, 2.0))
        
        return client.get_diagnostics(abs_path)
    
    return []


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
    "init",
    "diagnostics",
    "touch_file",
    "status",
    "shutdown",
    "Diagnostic",
    "LSPClient",
    "SERVERS",
    "get_server_for_file",
]
