"""Discover and load AGENTS.md / CLAUDE.md rule files"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


LOCAL_RULE_FILES = [
    "AGENTS.md",
    "AGENT.md", 
    "CLAUDE.md",
    "CONTEXT.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
]

GLOBAL_LOCATIONS = [
    Path.home() / ".config" / "codesm" / "AGENTS.md",
    Path.home() / ".config" / "opencode" / "AGENTS.md",
    Path.home() / ".claude" / "CLAUDE.md",
]


@dataclass
class RuleFile:
    """A discovered rule file"""
    path: Path
    content: str
    is_global: bool = False
    
    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class RulesDiscovery:
    """Discovers and manages rule files for a workspace"""
    
    workspace: Path
    root: Optional[Path] = None
    _rules: list[RuleFile] = field(default_factory=list)
    _discovered: bool = False
    
    def __post_init__(self):
        self.workspace = Path(self.workspace).resolve()
        if self.root:
            self.root = Path(self.root).resolve()
    
    def discover(self) -> list[RuleFile]:
        """Find all applicable rule files"""
        if self._discovered:
            return self._rules
        
        self._rules = []
        found_paths = set()
        
        local_rules = self._find_local_rules()
        for rule in local_rules:
            if rule.path not in found_paths:
                self._rules.append(rule)
                found_paths.add(rule.path)
        
        global_rules = self._find_global_rules()
        for rule in global_rules:
            if rule.path not in found_paths:
                self._rules.append(rule)
                found_paths.add(rule.path)
        
        self._discovered = True
        return self._rules
    
    def _find_local_rules(self) -> list[RuleFile]:
        """Find rule files by walking up from workspace"""
        rules = []
        
        current = self.workspace
        stop_at = self.root or Path(current.anchor)
        
        while current >= stop_at:
            for filename in LOCAL_RULE_FILES:
                candidate = current / filename
                if candidate.is_file():
                    try:
                        content = candidate.read_text(encoding="utf-8")
                        rules.append(RuleFile(
                            path=candidate,
                            content=content,
                            is_global=False,
                        ))
                    except Exception:
                        pass
            
            if current == stop_at:
                break
            parent = current.parent
            if parent == current:
                break
            current = parent
        
        return rules
    
    def _find_global_rules(self) -> list[RuleFile]:
        """Find global rule files"""
        rules = []
        
        for location in GLOBAL_LOCATIONS:
            if location.is_file():
                try:
                    content = location.read_text(encoding="utf-8")
                    rules.append(RuleFile(
                        path=location,
                        content=content,
                        is_global=True,
                    ))
                    break
                except Exception:
                    pass
        
        return rules
    
    def get_combined_rules(self) -> str:
        """Get all rules combined into a single string for system prompt"""
        rules = self.discover()
        if not rules:
            return ""
        
        sections = []
        for rule in rules:
            header = f"# Instructions from: {rule.path}"
            if rule.is_global:
                header += " (global)"
            sections.append(f"{header}\n\n{rule.content}")
        
        return "\n\n---\n\n".join(sections)
    
    def get_rules_summary(self) -> str:
        """Get a short summary of discovered rules"""
        rules = self.discover()
        if not rules:
            return "No AGENTS.md or rule files found."
        
        lines = [f"Found {len(rules)} rule file(s):"]
        for rule in rules:
            scope = "global" if rule.is_global else "local"
            lines.append(f"  - {rule.path} ({scope})")
        return "\n".join(lines)
    
    def refresh(self):
        """Re-discover rules (call after changes)"""
        self._discovered = False
        self._rules = []
        return self.discover()


def discover_rules(workspace: Path, root: Optional[Path] = None) -> str:
    """Convenience function to discover and return combined rules"""
    discovery = RulesDiscovery(workspace=workspace, root=root)
    return discovery.get_combined_rules()
