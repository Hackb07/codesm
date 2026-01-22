"""Initialize AGENTS.md by scanning the project"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ProjectInfo:
    """Detected project information"""
    name: str = ""
    description: str = ""
    language: str = ""
    package_manager: str = ""
    build_command: str = ""
    test_command: str = ""
    lint_command: str = ""
    dev_command: str = ""
    format_command: str = ""
    frameworks: list[str] = field(default_factory=list)
    has_typescript: bool = False
    has_eslint: bool = False
    has_prettier: bool = False
    has_ruff: bool = False
    has_mypy: bool = False
    has_black: bool = False
    # Project structure
    key_directories: dict[str, str] = field(default_factory=dict)
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    # Git info
    git_branch: str = ""
    recent_contributors: list[str] = field(default_factory=list)


def scan_project(workspace: Path) -> ProjectInfo:
    """Scan a project directory to detect its configuration"""
    info = ProjectInfo()
    
    # Get project name from directory
    info.name = workspace.name
    
    # Scan for key directories
    info.key_directories = _scan_directories(workspace)
    
    # Scan for config files
    info.config_files = _scan_config_files(workspace)
    
    # Get git info
    _scan_git_info(workspace, info)
    
    # Check for package.json (Node.js)
    package_json = workspace / "package.json"
    if package_json.exists():
        _scan_nodejs_project(workspace, info, package_json)
    
    # Check for pyproject.toml (Python)
    pyproject = workspace / "pyproject.toml"
    if pyproject.exists() and not info.language:
        _scan_python_project(workspace, info, pyproject)
    
    # Check for Cargo.toml (Rust)
    cargo = workspace / "Cargo.toml"
    if cargo.exists() and not info.language:
        info.language = "Rust"
        info.package_manager = "cargo"
        info.build_command = "cargo build"
        info.test_command = "cargo test"
        info.lint_command = "cargo clippy"
        info.format_command = "cargo fmt"
        info.frameworks.append("Rust")
        info.entry_points = ["src/main.rs", "src/lib.rs"]
    
    # Check for go.mod (Go)
    gomod = workspace / "go.mod"
    if gomod.exists() and not info.language:
        info.language = "Go"
        info.package_manager = "go"
        info.build_command = "go build ./..."
        info.test_command = "go test ./..."
        info.lint_command = "golangci-lint run"
        info.format_command = "gofmt -w ."
        info.frameworks.append("Go")
        # Find main.go
        for p in workspace.rglob("main.go"):
            info.entry_points.append(str(p.relative_to(workspace)))
    
    return info


def _scan_directories(workspace: Path) -> dict[str, str]:
    """Scan for key directories and their purposes"""
    dirs = {}
    
    common_dirs = {
        "src": "Source code",
        "lib": "Library code",
        "app": "Application code",
        "core": "Core functionality",
        "api": "API endpoints",
        "components": "UI components",
        "pages": "Page components",
        "routes": "Route handlers",
        "models": "Data models",
        "services": "Business logic services",
        "utils": "Utility functions",
        "helpers": "Helper functions",
        "hooks": "React hooks",
        "tests": "Test files",
        "test": "Test files",
        "__tests__": "Test files",
        "spec": "Test specifications",
        "docs": "Documentation",
        "scripts": "Build/utility scripts",
        "config": "Configuration files",
        "public": "Static assets",
        "static": "Static files",
        "assets": "Asset files",
        "migrations": "Database migrations",
        "fixtures": "Test fixtures",
        "mocks": "Mock data/functions",
        "types": "Type definitions",
        "interfaces": "Interface definitions",
        "schemas": "Data schemas",
        "templates": "Template files",
        "views": "View templates",
        "controllers": "Controller logic",
        "middleware": "Middleware functions",
        "plugins": "Plugin modules",
        "extensions": "Extension modules",
    }
    
    for name, desc in common_dirs.items():
        path = workspace / name
        if path.is_dir():
            # Count files to verify it's not empty
            file_count = sum(1 for _ in path.rglob("*") if _.is_file())
            if file_count > 0:
                dirs[name] = desc
    
    return dirs


def _scan_config_files(workspace: Path) -> list[str]:
    """Find configuration files in the project"""
    configs = []
    
    config_patterns = [
        "*.config.js", "*.config.ts", "*.config.mjs",
        ".eslintrc*", ".prettierrc*", ".babelrc*",
        "tsconfig*.json", "jsconfig.json",
        "pyproject.toml", "setup.py", "setup.cfg",
        "Cargo.toml", "go.mod",
        "Makefile", "Dockerfile", "docker-compose*.yml",
        ".env.example", ".env.sample",
        "package.json", "requirements*.txt",
    ]
    
    for pattern in config_patterns:
        for f in workspace.glob(pattern):
            if f.is_file():
                configs.append(f.name)
    
    return sorted(set(configs))


def _scan_git_info(workspace: Path, info: ProjectInfo):
    """Get git information"""
    try:
        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            info.git_branch = result.stdout.strip()
        
        # Get recent contributors
        result = subprocess.run(
            ["git", "log", "--format=%an", "-20"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            contributors = list(dict.fromkeys(result.stdout.strip().split("\n")))[:5]
            info.recent_contributors = [c for c in contributors if c]
    except Exception:
        pass


def _scan_nodejs_project(workspace: Path, info: ProjectInfo, package_json: Path):
    """Scan Node.js/JavaScript/TypeScript project"""
    try:
        data = json.loads(package_json.read_text())
        info.name = data.get("name", workspace.name)
        info.description = data.get("description", "")
        info.language = "TypeScript" if (workspace / "tsconfig.json").exists() else "JavaScript"
        info.has_typescript = (workspace / "tsconfig.json").exists()
        
        # Detect package manager
        if (workspace / "pnpm-lock.yaml").exists():
            info.package_manager = "pnpm"
        elif (workspace / "yarn.lock").exists():
            info.package_manager = "yarn"
        elif (workspace / "bun.lockb").exists():
            info.package_manager = "bun"
        else:
            info.package_manager = "npm"
        
        # Extract scripts
        scripts = data.get("scripts", {})
        pm = info.package_manager
        
        if "build" in scripts:
            info.build_command = f"{pm} run build"
        if "test" in scripts:
            info.test_command = f"{pm} run test"
        if "lint" in scripts:
            info.lint_command = f"{pm} run lint"
        if "format" in scripts:
            info.format_command = f"{pm} run format"
        if "dev" in scripts:
            info.dev_command = f"{pm} run dev"
        elif "start" in scripts:
            info.dev_command = f"{pm} run start"
        
        # Detect frameworks
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        
        framework_map = {
            "react": "React",
            "vue": "Vue",
            "svelte": "Svelte",
            "next": "Next.js",
            "nuxt": "Nuxt",
            "express": "Express",
            "fastify": "Fastify",
            "nestjs": "NestJS",
            "@nestjs/core": "NestJS",
            "hono": "Hono",
            "koa": "Koa",
            "gatsby": "Gatsby",
            "remix": "Remix",
            "@remix-run/react": "Remix",
            "astro": "Astro",
            "electron": "Electron",
            "tailwindcss": "Tailwind CSS",
            "@angular/core": "Angular",
        }
        
        for dep, name in framework_map.items():
            if dep in deps and name not in info.frameworks:
                info.frameworks.append(name)
        
        info.has_eslint = "eslint" in deps or (workspace / ".eslintrc.js").exists() or (workspace / ".eslintrc.json").exists()
        info.has_prettier = "prettier" in deps or (workspace / ".prettierrc").exists() or (workspace / ".prettierrc.json").exists()
        
        # Find entry points
        main = data.get("main")
        if main:
            info.entry_points.append(main)
        
        # Common entry points
        for ep in ["src/index.ts", "src/index.js", "src/main.ts", "src/main.js", "index.js", "index.ts"]:
            if (workspace / ep).exists() and ep not in info.entry_points:
                info.entry_points.append(ep)
                
    except Exception:
        pass


def _scan_python_project(workspace: Path, info: ProjectInfo, pyproject: Path):
    """Scan Python project"""
    info.language = "Python"
    
    # Try to parse pyproject.toml for more info
    try:
        import tomllib
        data = tomllib.loads(pyproject.read_text())
        
        # Get project info
        project = data.get("project", {})
        info.name = project.get("name", workspace.name)
        info.description = project.get("description", "")
        
        # Check for tools
        tool = data.get("tool", {})
        if "ruff" in tool:
            info.has_ruff = True
        if "mypy" in tool:
            info.has_mypy = True
        if "black" in tool:
            info.has_black = True
        if "pytest" in tool:
            pass  # pytest config exists
            
        # Get scripts
        scripts = project.get("scripts", {})
        if scripts:
            info.entry_points = list(scripts.keys())
            
    except Exception:
        pass
    
    # Detect package manager
    if (workspace / "uv.lock").exists():
        info.package_manager = "uv"
        info.build_command = "uv build"
        info.test_command = "uv run pytest"
        if info.has_ruff:
            info.lint_command = "uv run ruff check ."
            info.format_command = "uv run ruff format ."
        elif info.has_black:
            info.format_command = "uv run black ."
    elif (workspace / "poetry.lock").exists():
        info.package_manager = "poetry"
        info.build_command = "poetry build"
        info.test_command = "poetry run pytest"
        if info.has_ruff:
            info.lint_command = "poetry run ruff check ."
            info.format_command = "poetry run ruff format ."
    elif (workspace / "Pipfile.lock").exists():
        info.package_manager = "pipenv"
        info.test_command = "pipenv run pytest"
    else:
        info.package_manager = "pip"
        info.test_command = "pytest"
        if info.has_ruff:
            info.lint_command = "ruff check ."
            info.format_command = "ruff format ."
    
    # Find Python packages
    for item in workspace.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            if item.name not in ["tests", "test", "docs", "examples", "scripts"]:
                info.entry_points.append(f"{item.name}/")
    
    # Check for main.py
    if (workspace / "main.py").exists():
        info.entry_points.insert(0, "main.py")
    
    info.frameworks.append("Python")


def generate_agents_md(info: ProjectInfo, workspace: Path) -> str:
    """Generate AGENTS.md content based on project info"""
    lines = []
    
    # Header
    project_name = info.name or workspace.name
    lines.append(f"# {project_name}")
    lines.append("")
    
    # Description
    if info.description:
        lines.append(info.description)
        lines.append("")
    
    if info.language:
        tech_stack = [info.language]
        for fw in info.frameworks:
            if fw != info.language and fw not in tech_stack:
                tech_stack.append(fw)
        lines.append(f"**Tech Stack:** {', '.join(tech_stack)}")
        lines.append("")
    
    # Project Structure
    if info.key_directories:
        lines.append("## Project Structure")
        lines.append("")
        lines.append("```")
        for dir_name, desc in sorted(info.key_directories.items()):
            lines.append(f"{dir_name}/    # {desc}")
        lines.append("```")
        lines.append("")
    
    # Entry Points
    if info.entry_points:
        lines.append("## Entry Points")
        lines.append("")
        for ep in info.entry_points[:5]:  # Limit to 5
            lines.append(f"- `{ep}`")
        lines.append("")
    
    # Commands section
    has_commands = any([info.build_command, info.test_command, info.lint_command, info.dev_command, info.format_command])
    if has_commands:
        lines.append("## Commands")
        lines.append("")
        lines.append("```bash")
        if info.dev_command:
            lines.append(f"# Development")
            lines.append(info.dev_command)
            lines.append("")
        if info.build_command:
            lines.append(f"# Build")
            lines.append(info.build_command)
            lines.append("")
        if info.test_command:
            lines.append(f"# Test")
            lines.append(info.test_command)
            lines.append("")
        if info.lint_command:
            lines.append(f"# Lint")
            lines.append(info.lint_command)
            lines.append("")
        if info.format_command:
            lines.append(f"# Format")
            lines.append(info.format_command)
        lines.append("```")
        lines.append("")
    
    # Code style section
    lines.append("## Code Style")
    lines.append("")
    
    if info.has_typescript:
        lines.append("- Use TypeScript with strict mode enabled")
        lines.append("- Prefer `interface` over `type` for object shapes")
    if info.has_eslint:
        lines.append("- Follow ESLint rules - run lint before committing")
    if info.has_prettier:
        lines.append("- Format with Prettier - formatting is enforced")
    if info.has_ruff:
        lines.append("- Use Ruff for linting and formatting")
    if info.has_mypy:
        lines.append("- Type hints required - mypy strict mode")
    if info.has_black:
        lines.append("- Format with Black")
    
    if info.language == "Python":
        lines.append("- Use type hints for all function signatures")
        lines.append("- Follow PEP 8 style guide")
        lines.append("- Use dataclasses or Pydantic for data structures")
    elif info.language == "TypeScript" or info.language == "JavaScript":
        lines.append("- Use async/await over callbacks")
        lines.append("- Prefer const over let")
    elif info.language == "Rust":
        lines.append("- Follow Rust idioms and clippy suggestions")
        lines.append("- Use `?` operator for error propagation")
    elif info.language == "Go":
        lines.append("- Follow Go conventions")
        lines.append("- Handle all errors explicitly")
    
    lines.append("- Match existing code patterns in the codebase")
    lines.append("")
    
    # Guidelines section
    lines.append("## Guidelines")
    lines.append("")
    lines.append("- Keep changes focused and minimal")
    lines.append("- Write tests for new functionality")
    lines.append("- Update documentation for API changes")
    lines.append("- Don't add unnecessary comments - code should be self-documenting")
    lines.append("- Prefer composition over inheritance")
    lines.append("")
    
    # Workflow section
    lines.append("## Workflow")
    lines.append("")
    if info.test_command:
        lines.append(f"1. Make changes")
        lines.append(f"2. Run tests: `{info.test_command}`")
        if info.lint_command:
            lines.append(f"3. Run linter: `{info.lint_command}`")
        lines.append(f"4. Commit with descriptive message")
    else:
        lines.append("1. Make changes")
        lines.append("2. Test your changes manually")
        lines.append("3. Commit with descriptive message")
    lines.append("")
    
    # Config files
    if info.config_files:
        lines.append("## Configuration")
        lines.append("")
        lines.append("Key config files: " + ", ".join(f"`{f}`" for f in info.config_files[:8]))
        lines.append("")
    
    return "\n".join(lines)


def init_agents_md(workspace: Path, force: bool = False) -> tuple[str, bool]:
    """
    Initialize AGENTS.md for a project.
    
    Returns:
        Tuple of (content, already_exists)
    """
    agents_path = workspace / "AGENTS.md"
    
    if agents_path.exists() and not force:
        return agents_path.read_text(), True
    
    info = scan_project(workspace)
    content = generate_agents_md(info, workspace)
    
    return content, False


def save_agents_md(workspace: Path, content: str) -> Path:
    """Save AGENTS.md to the workspace"""
    agents_path = workspace / "AGENTS.md"
    agents_path.write_text(content)
    return agents_path
