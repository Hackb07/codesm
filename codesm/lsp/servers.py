"""LSP server configurations"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ServerConfig:
    name: str
    command: list[str]
    file_extensions: list[str]
    root_uri_required: bool = True


SERVERS: dict[str, ServerConfig] = {
    "python": ServerConfig(
        name="pylsp",
        command=["pylsp"],
        file_extensions=[".py", ".pyi"],
    ),
    "python-pyright": ServerConfig(
        name="pyright",
        command=["pyright-langserver", "--stdio"],
        file_extensions=[".py", ".pyi"],
    ),
    "typescript": ServerConfig(
        name="typescript-language-server",
        command=["typescript-language-server", "--stdio"],
        file_extensions=[".ts", ".tsx", ".js", ".jsx"],
    ),
    "rust": ServerConfig(
        name="rust-analyzer",
        command=["rust-analyzer"],
        file_extensions=[".rs"],
    ),
    "go": ServerConfig(
        name="gopls",
        command=["gopls", "serve"],
        file_extensions=[".go"],
    ),
}


def get_server_for_file(path: str) -> Optional[str]:
    """Get the server key for a given file path."""
    for key, config in SERVERS.items():
        for ext in config.file_extensions:
            if path.endswith(ext):
                return key
    return None
