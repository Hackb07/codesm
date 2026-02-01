"""LSP server configurations"""

from dataclasses import dataclass, field


@dataclass
class ServerConfig:
    name: str
    command: list[str]
    file_extensions: list[str]
    root_uri_required: bool = True
    priority: int = 0
    root_markers: list[str] = field(default_factory=list)


SERVERS: dict[str, ServerConfig] = {
    "python": ServerConfig(
        name="pylsp",
        command=["pylsp"],
        file_extensions=[".py", ".pyi"],
        root_markers=["pyproject.toml", "setup.py", "requirements.txt"],
    ),
    "python-pyright": ServerConfig(
        name="pyright",
        command=["pyright-langserver", "--stdio"],
        file_extensions=[".py", ".pyi"],
        root_markers=["pyproject.toml", "pyrightconfig.json"],
    ),
    "typescript": ServerConfig(
        name="typescript-language-server",
        command=["typescript-language-server", "--stdio"],
        file_extensions=[".ts", ".tsx", ".js", ".jsx"],
        root_markers=["package.json", "tsconfig.json"],
    ),
    "rust": ServerConfig(
        name="rust-analyzer",
        command=["rust-analyzer"],
        file_extensions=[".rs"],
        root_markers=["Cargo.toml"],
    ),
    "go": ServerConfig(
        name="gopls",
        command=["gopls", "serve"],
        file_extensions=[".go"],
        root_markers=["go.mod"],
    ),
    "vue": ServerConfig(
        name="vue-language-server",
        command=["vue-language-server", "--stdio"],
        file_extensions=[".vue"],
        root_markers=["package.json"],
    ),
    "svelte": ServerConfig(
        name="svelteserver",
        command=["svelteserver", "--stdio"],
        file_extensions=[".svelte"],
        root_markers=["package.json", "svelte.config.js"],
    ),
    "eslint": ServerConfig(
        name="vscode-eslint-language-server",
        command=["vscode-eslint-language-server", "--stdio"],
        file_extensions=[".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte"],
        priority=10,
        root_markers=[".eslintrc", ".eslintrc.js", ".eslintrc.json", "eslint.config.js"],
    ),
    "clangd": ServerConfig(
        name="clangd",
        command=["clangd"],
        file_extensions=[".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh"],
        root_markers=["compile_commands.json", "CMakeLists.txt"],
    ),
    "html": ServerConfig(
        name="vscode-html-language-server",
        command=["vscode-html-language-server", "--stdio"],
        file_extensions=[".html", ".htm"],
    ),
    "css": ServerConfig(
        name="vscode-css-language-server",
        command=["vscode-css-language-server", "--stdio"],
        file_extensions=[".css", ".scss", ".less"],
    ),
    "json": ServerConfig(
        name="vscode-json-language-server",
        command=["vscode-json-language-server", "--stdio"],
        file_extensions=[".json", ".jsonc"],
    ),
    "yaml": ServerConfig(
        name="yaml-language-server",
        command=["yaml-language-server", "--stdio"],
        file_extensions=[".yaml", ".yml"],
    ),
    "bash": ServerConfig(
        name="bash-language-server",
        command=["bash-language-server", "start"],
        file_extensions=[".sh", ".bash"],
    ),
    "lua": ServerConfig(
        name="lua-language-server",
        command=["lua-language-server"],
        file_extensions=[".lua"],
        root_markers=[".luarc.json"],
    ),
    "zig": ServerConfig(
        name="zls",
        command=["zls"],
        file_extensions=[".zig"],
        root_markers=["build.zig"],
    ),
    "java": ServerConfig(
        name="jdtls",
        command=["jdtls"],
        file_extensions=[".java"],
        root_markers=["pom.xml", "build.gradle"],
    ),
    "kotlin": ServerConfig(
        name="kotlin-language-server",
        command=["kotlin-language-server"],
        file_extensions=[".kt", ".kts"],
        root_markers=["build.gradle.kts", "build.gradle"],
    ),
    "csharp": ServerConfig(
        name="OmniSharp",
        command=["OmniSharp", "-lsp"],
        file_extensions=[".cs"],
        root_markers=["*.csproj", "*.sln"],
    ),
    "php": ServerConfig(
        name="phpactor",
        command=["phpactor", "language-server"],
        file_extensions=[".php"],
        root_markers=["composer.json"],
    ),
    "ruby": ServerConfig(
        name="solargraph",
        command=["solargraph", "stdio"],
        file_extensions=[".rb"],
        root_markers=["Gemfile"],
    ),
    "elixir": ServerConfig(
        name="elixir-ls",
        command=["elixir-ls"],
        file_extensions=[".ex", ".exs"],
        root_markers=["mix.exs"],
    ),
    "haskell": ServerConfig(
        name="haskell-language-server-wrapper",
        command=["haskell-language-server-wrapper", "--lsp"],
        file_extensions=[".hs"],
        root_markers=["stack.yaml", "cabal.project"],
    ),
    "ocaml": ServerConfig(
        name="ocamllsp",
        command=["ocamllsp"],
        file_extensions=[".ml", ".mli"],
        root_markers=["dune-project"],
    ),
    "scala": ServerConfig(
        name="metals",
        command=["metals"],
        file_extensions=[".scala", ".sc"],
        root_markers=["build.sbt"],
    ),
    "swift": ServerConfig(
        name="sourcekit-lsp",
        command=["sourcekit-lsp"],
        file_extensions=[".swift"],
        root_markers=["Package.swift"],
    ),
    "dart": ServerConfig(
        name="dart-language-server",
        command=["dart", "language-server"],
        file_extensions=[".dart"],
        root_markers=["pubspec.yaml"],
    ),
    "terraform": ServerConfig(
        name="terraform-ls",
        command=["terraform-ls", "serve"],
        file_extensions=[".tf", ".tfvars"],
        root_markers=[".terraform"],
    ),
}


LANGUAGE_IDS: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".rs": "rust",
    ".go": "go",
    ".vue": "vue",
    ".svelte": "svelte",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".json": "json",
    ".jsonc": "jsonc",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "shellscript",
    ".bash": "shellscript",
    ".lua": "lua",
    ".zig": "zig",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".ex": "elixir",
    ".exs": "elixir",
    ".hs": "haskell",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".scala": "scala",
    ".sc": "scala",
    ".swift": "swift",
    ".dart": "dart",
    ".tf": "terraform",
    ".tfvars": "terraform",
}


def get_servers_for_file(path: str) -> list[str]:
    """Get all matching server keys for a given file path, sorted by priority."""
    matching = []
    for key, config in SERVERS.items():
        for ext in config.file_extensions:
            if path.endswith(ext):
                matching.append((config.priority, key))
                break
    matching.sort(key=lambda x: x[0])
    return [key for _, key in matching]


def get_server_for_file(path: str) -> str | None:
    """Get the highest priority server key for a given file path."""
    servers = get_servers_for_file(path)
    return servers[0] if servers else None
