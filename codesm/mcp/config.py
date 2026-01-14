"""MCP configuration loading utilities"""

import json
import logging
from pathlib import Path
from typing import Any

from .client import MCPServerConfig

logger = logging.getLogger(__name__)


def load_mcp_config(config_path: Path | str | None = None) -> dict[str, MCPServerConfig]:
    """Load MCP server configurations from a JSON file.
    
    Supports formats compatible with:
    - Claude Desktop (mcpServers in claude_desktop_config.json)
    - OpenCode (mcp_servers in opencode.json)
    - Standalone MCP config file
    
    Args:
        config_path: Path to the config file. If None, searches for default locations.
        
    Returns:
        Dictionary mapping server names to MCPServerConfig
    """
    servers: dict[str, MCPServerConfig] = {}
    
    # Search paths if none provided
    if config_path is None:
        search_paths = [
            Path.cwd() / "codesm.json",
            Path.cwd() / ".codesm" / "mcp.json",
            Path.cwd() / "mcp-servers.json",
            Path.home() / ".config" / "codesm" / "mcp.json",
            Path.home() / ".codesm" / "mcp.json",
        ]
    else:
        search_paths = [Path(config_path)]
    
    for path in search_paths:
        if path.exists():
            try:
                config = json.loads(path.read_text())
                servers = _parse_mcp_config(config)
                if servers:
                    logger.info(f"Loaded {len(servers)} MCP servers from {path}")
                    return servers
            except Exception as e:
                logger.warning(f"Failed to load MCP config from {path}: {e}")
    
    return servers


def _parse_mcp_config(config: dict[str, Any]) -> dict[str, MCPServerConfig]:
    """Parse MCP server configurations from various config formats"""
    servers: dict[str, MCPServerConfig] = {}
    
    # Try different config formats
    mcp_config = None
    
    # Format 1: Direct mcpServers (Claude Desktop style)
    if "mcpServers" in config:
        mcp_config = config["mcpServers"]
    
    # Format 2: Nested under mcp.servers (OpenCode style)
    elif "mcp" in config and isinstance(config["mcp"], dict):
        if "servers" in config["mcp"]:
            mcp_config = config["mcp"]["servers"]
        else:
            mcp_config = config["mcp"]
    
    # Format 3: Direct servers dict
    elif "servers" in config:
        mcp_config = config["servers"]
    
    # Format 4: Root level is servers dict
    elif all(isinstance(v, dict) and "command" in v for v in config.values()):
        mcp_config = config
    
    if not mcp_config:
        return servers
    
    # Parse each server
    for name, server_config in mcp_config.items():
        if not isinstance(server_config, dict):
            continue
        
        # Skip if no command specified
        if "command" not in server_config:
            logger.warning(f"MCP server '{name}' has no command, skipping")
            continue
        
        try:
            servers[name] = MCPServerConfig(
                name=name,
                command=server_config["command"],
                args=server_config.get("args", []),
                env=server_config.get("env", {}),
                transport=server_config.get("transport", "stdio"),
                url=server_config.get("url"),
            )
        except Exception as e:
            logger.warning(f"Failed to parse MCP server '{name}': {e}")
    
    return servers


def create_example_config(path: Path | str = "mcp-servers.json"):
    """Create an example MCP configuration file"""
    example = {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            },
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": "<your-token>"
                },
            },
            "sqlite": {
                "command": "uvx",
                "args": ["mcp-server-sqlite", "--db-path", "database.db"],
            },
        }
    }
    
    path = Path(path)
    path.write_text(json.dumps(example, indent=2))
    logger.info(f"Created example MCP config at {path}")
    return path
