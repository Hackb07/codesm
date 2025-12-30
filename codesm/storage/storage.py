"""File-based storage"""

import json
from pathlib import Path
from typing import Any


class Storage:
    BASE_DIR = Path.home() / ".local" / "share" / "codesm"
    
    @classmethod
    def _key_to_path(cls, key: list[str]) -> Path:
        return cls.BASE_DIR / f"{'/'.join(key)}.json"
    
    @classmethod
    def write(cls, key: list[str], data: Any):
        """Write data to storage"""
        path = cls._key_to_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
    
    @classmethod
    def read(cls, key: list[str]) -> Any | None:
        """Read data from storage"""
        path = cls._key_to_path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    
    @classmethod
    def delete(cls, key: list[str]):
        """Delete data from storage"""
        path = cls._key_to_path(key)
        if path.exists():
            path.unlink()
    
    @classmethod
    def list(cls, prefix: list[str]) -> list[list[str]]:
        """List all keys with given prefix"""
        dir_path = cls.BASE_DIR / "/".join(prefix) if prefix else cls.BASE_DIR
        if not dir_path.exists():
            return []

        keys = []
        for path in dir_path.rglob("*.json"):
            rel = path.relative_to(cls.BASE_DIR)
            key = list(rel.with_suffix("").parts)
            keys.append(key)
        return keys
