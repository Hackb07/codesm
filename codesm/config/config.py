"""Configuration management"""

from pathlib import Path
from pydantic import BaseModel
from typing import Any
import json


class ProviderConfig(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    options: dict[str, Any] = {}


class AgentConfig(BaseModel):
    name: str
    model: str | None = None
    prompt: str | None = None
    tools: dict[str, bool] = {}
    permissions: dict[str, str] = {}


class Config(BaseModel):
    model: str = "anthropic/claude-sonnet-4-20250514"
    providers: dict[str, ProviderConfig] = {}
    agents: dict[str, AgentConfig] = {}
    
    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load config from file"""
        if path is None:
            # Look for codesm.json in current dir or home
            candidates = [
                Path.cwd() / "codesm.json",
                Path.home() / ".config" / "codesm" / "config.json",
            ]
            for p in candidates:
                if p.exists():
                    path = p
                    break
        
        if path and path.exists():
            data = json.loads(path.read_text())
            return cls(**data)
        
        return cls()
    
    def save(self, path: Path):
        """Save config to file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2))
