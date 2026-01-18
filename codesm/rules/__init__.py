"""Rules discovery - finds and loads AGENTS.md and similar rule files"""

from .discovery import RulesDiscovery, discover_rules
from .init import scan_project, init_agents_md, save_agents_md, ProjectInfo

__all__ = [
    "RulesDiscovery", 
    "discover_rules",
    "scan_project",
    "init_agents_md", 
    "save_agents_md",
    "ProjectInfo",
]
