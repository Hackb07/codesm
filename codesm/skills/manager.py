"""Skill manager - discovers, loads, and manages markdown-based skills"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .loader import SkillLoader, Skill

logger = logging.getLogger(__name__)


@dataclass
class SkillSummary:
    """Lightweight skill info for listing"""
    name: str
    description: str
    triggers: list[str]
    path: Path
    is_active: bool = False


class SkillManager:
    """
    Manages markdown-based skills that inject instructions into the agent prompt.
    
    Skills are discovered from:
    - {workspace}/.codesm/skills/**/SKILL.md
    - {workspace}/skills/**/SKILL.md
    
    Workspace skills take precedence over .codesm skills.
    """
    
    # Max total size of injected skill content (prevent prompt bloat)
    MAX_INJECTED_SIZE = 40_000
    
    def __init__(
        self,
        workspace_dir: Path,
        skills_dirs: list[str] | None = None,
        auto_triggers_enabled: bool = True,
    ):
        self.workspace_dir = Path(workspace_dir).resolve()
        self.skills_dirs = skills_dirs or [".codesm/skills", "skills", "examples/skills"]
        self.auto_triggers_enabled = auto_triggers_enabled
        
        self._discovered: dict[str, Skill] = {}
        self._active: dict[str, Skill] = {}
        self._triggered_this_session: set[str] = set()
        
        # Discover on init
        self.discover()
    
    def discover(self) -> dict[str, Skill]:
        """Scan skill directories and discover all SKILL.md files"""
        self._discovered.clear()
        
        for rel_dir in self.skills_dirs:
            skills_path = self.workspace_dir / rel_dir
            if not skills_path.exists():
                continue
            
            # Find all SKILL.md files recursively
            for skill_file in skills_path.rglob("SKILL.md"):
                try:
                    skill = SkillLoader.load(skill_file)
                    
                    # Handle name collisions (later dirs win)
                    if skill.name in self._discovered:
                        logger.debug(f"Skill '{skill.name}' overridden by {skill_file}")
                    
                    self._discovered[skill.name] = skill
                    logger.debug(f"Discovered skill: {skill.name} at {skill_file}")
                    
                except Exception as e:
                    logger.warning(f"Failed to load skill from {skill_file}: {e}")
        
        logger.info(f"Discovered {len(self._discovered)} skills")
        return self._discovered
    
    def list(self) -> list[SkillSummary]:
        """List all discovered skills"""
        return [
            SkillSummary(
                name=skill.name,
                description=skill.description,
                triggers=skill.triggers,
                path=skill.path,
                is_active=skill.name in self._active,
            )
            for skill in self._discovered.values()
        ]
    
    def get(self, name: str) -> Skill | None:
        """Get a skill by name"""
        return self._discovered.get(name)
    
    def load(self, name: str) -> Skill | None:
        """Load a skill by name (add to active set)"""
        skill = self._discovered.get(name)
        if not skill:
            return None
        
        self._active[name] = skill
        logger.info(f"Loaded skill: {name}")
        return skill
    
    def unload(self, name: str) -> bool:
        """Unload a skill by name"""
        if name in self._active:
            del self._active[name]
            # Also remove from triggered set so it can trigger again
            self._triggered_this_session.discard(name)
            logger.info(f"Unloaded skill: {name}")
            return True
        return False
    
    def active(self) -> list[Skill]:
        """Get list of currently active skills"""
        return list(self._active.values())
    
    def is_active(self, name: str) -> bool:
        """Check if a skill is active"""
        return name in self._active
    
    def auto_load_for_message(self, user_message: str) -> list[str]:
        """
        Check triggers and auto-load matching skills.
        Returns list of newly loaded skill names.
        """
        if not self.auto_triggers_enabled:
            return []
        
        newly_loaded = []
        
        for skill in self._discovered.values():
            # Skip if already active or already triggered this session
            if skill.name in self._active:
                continue
            if skill.name in self._triggered_this_session:
                continue
            
            # Check triggers
            for pattern in skill.triggers:
                try:
                    if re.search(pattern, user_message, re.IGNORECASE):
                        self._active[skill.name] = skill
                        self._triggered_this_session.add(skill.name)
                        newly_loaded.append(skill.name)
                        logger.info(f"Auto-loaded skill '{skill.name}' (trigger: {pattern})")
                        break
                except re.error as e:
                    logger.warning(f"Invalid trigger pattern in skill {skill.name}: {pattern} - {e}")
        
        return newly_loaded
    
    def render_active_for_prompt(self) -> str:
        """Render all active skills as a prompt block"""
        if not self._active:
            return ""
        
        parts = ["# Loaded Skills"]
        total_size = 0
        truncated = False
        
        for skill in self._active.values():
            skill_block = self._render_skill(skill)
            
            if total_size + len(skill_block) > self.MAX_INJECTED_SIZE:
                truncated = True
                break
            
            parts.append(skill_block)
            total_size += len(skill_block)
        
        if truncated:
            parts.append("\n[Warning: Some skills truncated due to size limit]")
        
        return "\n\n".join(parts)
    
    def _render_skill(self, skill: Skill) -> str:
        """Render a single skill for prompt injection"""
        lines = [
            f"<loaded_skill name=\"{skill.name}\">",
        ]
        
        if skill.description:
            lines.append(f"Description: {skill.description}")
            lines.append("")
        
        lines.append(skill.content)
        
        if skill.resources:
            lines.append("")
            lines.append("Resources available in skill folder:")
            for res in skill.resources[:10]:  # Limit shown resources
                lines.append(f"  - {res}")
            if len(skill.resources) > 10:
                lines.append(f"  ... and {len(skill.resources) - 10} more")
        
        lines.append("</loaded_skill>")
        
        return "\n".join(lines)
    
    def clear(self):
        """Clear all active skills"""
        self._active.clear()
        self._triggered_this_session.clear()
    
    def get_resource_path(self, skill_name: str, resource: str) -> Path | None:
        """
        Get the full path to a skill resource.
        Returns None if skill not found or resource path is invalid.
        """
        skill = self._discovered.get(skill_name)
        if not skill:
            return None
        
        # Resolve the resource path
        resource_path = (skill.root_dir / resource).resolve()
        
        # Security: ensure it's within the skill directory
        try:
            resource_path.relative_to(skill.root_dir)
        except ValueError:
            logger.warning(f"Attempted path traversal in skill {skill_name}: {resource}")
            return None
        
        if not resource_path.exists():
            return None
        
        return resource_path
