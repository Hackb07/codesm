"""Skill loader - parses SKILL.md files with frontmatter"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Skill:
    """A loaded skill definition"""
    name: str
    description: str
    triggers: list[str]
    content: str
    path: Path
    root_dir: Path
    resources: list[str] = field(default_factory=list)
    
    @property
    def id(self) -> str:
        """Skill identifier (same as name)"""
        return self.name


class SkillLoader:
    """Loads and parses SKILL.md files"""
    
    FRONTMATTER_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n',
        re.DOTALL
    )
    
    @classmethod
    def load(cls, path: Path) -> Skill:
        """Load a skill from a SKILL.md file"""
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Skill file not found: {path}")
        
        content = path.read_text(encoding="utf-8")
        root_dir = path.parent
        
        # Parse frontmatter
        frontmatter, body = cls._parse_frontmatter(content)
        
        # Extract fields
        name = frontmatter.get("name") or root_dir.name
        description = frontmatter.get("description", "")
        triggers = cls._parse_list(frontmatter.get("triggers", []))
        resources_explicit = cls._parse_list(frontmatter.get("resources", []))
        
        # Auto-discover resources if not explicitly listed
        if resources_explicit:
            resources = resources_explicit
        else:
            resources = cls._discover_resources(root_dir)
        
        return Skill(
            name=name,
            description=description,
            triggers=triggers,
            content=body.strip(),
            path=path,
            root_dir=root_dir,
            resources=resources,
        )
    
    @classmethod
    def _parse_frontmatter(cls, content: str) -> tuple[dict[str, Any], str]:
        """Parse YAML-like frontmatter from markdown content"""
        match = cls.FRONTMATTER_PATTERN.match(content)
        if not match:
            return {}, content
        
        frontmatter_text = match.group(1)
        body = content[match.end():]
        
        # Simple YAML-like parser (no dependency on PyYAML)
        frontmatter = cls._parse_simple_yaml(frontmatter_text)
        
        return frontmatter, body
    
    @classmethod
    def _parse_simple_yaml(cls, text: str) -> dict[str, Any]:
        """
        Parse simple YAML-like frontmatter.
        Supports:
        - key: value
        - key: [item1, item2]
        - key:
            - item1
            - item2
        """
        result = {}
        lines = text.split("\n")
        current_key = None
        current_list = None
        
        for line in lines:
            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            
            # Check for list item
            if stripped.startswith("- "):
                if current_key and current_list is not None:
                    item = stripped[2:].strip().strip('"').strip("'")
                    current_list.append(item)
                continue
            
            # Check for key: value
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                
                # Save previous list if any
                if current_key and current_list is not None:
                    result[current_key] = current_list
                
                current_key = key
                
                if not value:
                    # Start a new list
                    current_list = []
                elif value.startswith("[") and value.endswith("]"):
                    # Inline list: [item1, item2]
                    items = value[1:-1].split(",")
                    result[key] = [
                        item.strip().strip('"').strip("'")
                        for item in items
                        if item.strip()
                    ]
                    current_key = None
                    current_list = None
                else:
                    # Simple value
                    result[key] = value.strip('"').strip("'")
                    current_key = None
                    current_list = None
        
        # Save final list if any
        if current_key and current_list is not None:
            result[current_key] = current_list
        
        return result
    
    @classmethod
    def _parse_list(cls, value: Any) -> list[str]:
        """Ensure value is a list of strings"""
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, str):
            return [value] if value else []
        return []
    
    @classmethod
    def _discover_resources(cls, root_dir: Path) -> list[str]:
        """Auto-discover resource files in the skill directory"""
        resources = []
        
        for item in root_dir.rglob("*"):
            if item.is_file() and item.name != "SKILL.md":
                # Get relative path
                rel_path = item.relative_to(root_dir)
                resources.append(str(rel_path))
        
        return sorted(resources)
