"""Configuration schemas using Pydantic"""

from pydantic import BaseModel, Field
from pathlib import Path
from typing import Any, Literal


class ProviderConfig(BaseModel):
    """LLM provider configuration"""
    name: Literal["anthropic", "openai"]
    api_key: str | None = None
    base_url: str | None = None
    timeout: int = 120


class ModelConfig(BaseModel):
    """Model configuration"""
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-5-20250929"
    temperature: float = 0.7
    max_tokens: int = 8192


class ToolConfig(BaseModel):
    """Tool configuration"""
    enabled: list[str] = Field(default_factory=lambda: [
        "read", "write", "edit", "bash", "grep", "glob"
    ])
    disabled: list[str] = Field(default_factory=list)


class SessionConfig(BaseModel):
    """Session configuration"""
    auto_save: bool = True
    max_context_tokens: int = 100000
    compact_threshold: float = 0.8


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server"""
    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: Literal["stdio", "sse", "streamable-http"] = "stdio"
    url: str | None = None


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) configuration"""
    enabled: bool = True
    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class Config(BaseModel):
    """Main configuration"""
    model: ModelConfig = Field(default_factory=ModelConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    working_directory: Path = Field(default_factory=Path.cwd)

    class Config:
        arbitrary_types_allowed = True
