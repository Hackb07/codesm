"""Initialize AGENTS.md by scanning the project"""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ProjectInfo:
    """Detected project information"""
    name: str = ""
    language: str = ""
    package_manager: str = ""
    build_command: str = ""
    test_command: str = ""
    lint_command: str = ""
    dev_command: str = ""
    frameworks: list[str] = field(default_factory=list)
    has_typescript: bool = False
    has_eslint: bool = False
    has_prettier: bool = False


def scan_project(workspace: Path) -> ProjectInfo:
    """Scan a project directory to detect its configuration"""
    info = ProjectInfo()
    
    # Check for package.json (Node.js)
    package_json = workspace / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text())
            info.name = data.get("name", "")
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
            run = "run " if pm != "npm" else "run "
            
            if "build" in scripts:
                info.build_command = f"{pm} {run}build"
            if "test" in scripts:
                info.test_command = f"{pm} {run}test"
            if "lint" in scripts:
                info.lint_command = f"{pm} {run}lint"
            if "dev" in scripts:
                info.dev_command = f"{pm} {run}dev"
            elif "start" in scripts:
                info.dev_command = f"{pm} {run}start"
            
            # Detect frameworks
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "react" in deps:
                info.frameworks.append("React")
            if "vue" in deps:
                info.frameworks.append("Vue")
            if "svelte" in deps:
                info.frameworks.append("Svelte")
            if "next" in deps:
                info.frameworks.append("Next.js")
            if "express" in deps:
                info.frameworks.append("Express")
            if "fastify" in deps:
                info.frameworks.append("Fastify")
            
            info.has_eslint = "eslint" in deps or (workspace / ".eslintrc.js").exists()
            info.has_prettier = "prettier" in deps or (workspace / ".prettierrc").exists()
            
        except Exception:
            pass
    
    # Check for pyproject.toml (Python)
    pyproject = workspace / "pyproject.toml"
    if pyproject.exists() and not info.language:
        info.language = "Python"
        
        # Detect package manager
        if (workspace / "uv.lock").exists():
            info.package_manager = "uv"
            info.build_command = "uv build"
            info.test_command = "uv run pytest"
        elif (workspace / "poetry.lock").exists():
            info.package_manager = "poetry"
            info.build_command = "poetry build"
            info.test_command = "poetry run pytest"
        elif (workspace / "Pipfile.lock").exists():
            info.package_manager = "pipenv"
            info.test_command = "pipenv run pytest"
        else:
            info.package_manager = "pip"
            info.test_command = "pytest"
        
        info.frameworks.append("Python")
    
    # Check for Cargo.toml (Rust)
    cargo = workspace / "Cargo.toml"
    if cargo.exists() and not info.language:
        info.language = "Rust"
        info.package_manager = "cargo"
        info.build_command = "cargo build"
        info.test_command = "cargo test"
        info.lint_command = "cargo clippy"
        info.frameworks.append("Rust")
    
    # Check for go.mod (Go)
    gomod = workspace / "go.mod"
    if gomod.exists() and not info.language:
        info.language = "Go"
        info.package_manager = "go"
        info.build_command = "go build"
        info.test_command = "go test ./..."
        info.lint_command = "golangci-lint run"
        info.frameworks.append("Go")
    
    return info


def generate_agents_md(info: ProjectInfo, workspace: Path) -> str:
    """Generate AGENTS.md content based on project info"""
    lines = []
    
    # Header
    project_name = info.name or workspace.name
    lines.append(f"# {project_name}")
    lines.append("")
    
    if info.language:
        lines.append(f"This is a {info.language} project.")
        if info.frameworks:
            lines.append(f"Frameworks: {', '.join(info.frameworks)}")
        lines.append("")
    
    # Commands section
    if any([info.build_command, info.test_command, info.lint_command, info.dev_command]):
        lines.append("## Commands")
        lines.append("")
        if info.build_command:
            lines.append(f"- Build: `{info.build_command}`")
        if info.test_command:
            lines.append(f"- Test: `{info.test_command}`")
        if info.lint_command:
            lines.append(f"- Lint: `{info.lint_command}`")
        if info.dev_command:
            lines.append(f"- Dev: `{info.dev_command}`")
        lines.append("")
    
    # Code style section
    lines.append("## Code Style")
    lines.append("")
    
    if info.has_typescript:
        lines.append("- Use TypeScript with strict mode")
    if info.has_eslint:
        lines.append("- Follow ESLint rules")
    if info.has_prettier:
        lines.append("- Format with Prettier")
    
    if info.language == "Python":
        lines.append("- Use type hints")
        lines.append("- Follow PEP 8 style guide")
    elif info.language == "Rust":
        lines.append("- Follow Rust idioms")
        lines.append("- Use clippy suggestions")
    elif info.language == "Go":
        lines.append("- Follow Go conventions")
        lines.append("- Use gofmt for formatting")
    
    lines.append("- Match existing code patterns in the codebase")
    lines.append("")
    
    # Guidelines section
    lines.append("## Guidelines")
    lines.append("")
    lines.append("- Keep changes focused and minimal")
    lines.append("- Run tests before committing")
    lines.append("- Don't add unnecessary comments")
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
