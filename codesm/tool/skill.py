"""Skill tool - load and manage agent skills"""

from pathlib import Path
from .base import Tool


class SkillTool(Tool):
    """Tool for loading and managing skills that enhance agent behavior"""
    
    name = "skill"
    description = """Load specialized skills that provide domain-specific instructions and workflows.

When you recognize that a task matches one of the available skills, use this tool to load the full skill instructions.

The skill will inject detailed instructions, workflows, and access to bundled resources into the conversation context.

## Actions

- **list**: Show all available skills with their descriptions and triggers
- **load**: Load a skill by name to inject its instructions into context
- **unload**: Remove a loaded skill from context
- **active**: Show currently loaded skills
- **show**: Display the full content of a skill without loading it
- **resources**: List resources bundled with a skill
- **read_resource**: Read a specific resource file from a skill

## Examples

List available skills:
```json
{"action": "list"}
```

Load a skill:
```json
{"action": "load", "name": "frontend-reviewer"}
```

Show skill content without loading:
```json
{"action": "show", "name": "debugging"}
```

Read a skill resource:
```json
{"action": "read_resource", "name": "api-design", "resource": "templates/openapi.yaml"}
```
"""
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "load", "unload", "active", "show", "resources", "read_resource"],
                    "description": "Action to perform",
                },
                "name": {
                    "type": "string",
                    "description": "Skill name (required for load, unload, show, resources, read_resource)",
                },
                "resource": {
                    "type": "string",
                    "description": "Resource path relative to skill folder (for read_resource)",
                },
            },
            "required": ["action"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        action = args.get("action", "list")
        name = args.get("name")
        resource = args.get("resource")
        
        # Get skill manager from context
        skills = context.get("skills")
        if not skills:
            return "Error: Skill system not initialized"
        
        if action == "list":
            return self._list_skills(skills)
        
        elif action == "load":
            if not name:
                return "Error: 'name' parameter required for load action"
            return self._load_skill(skills, name)
        
        elif action == "unload":
            if not name:
                return "Error: 'name' parameter required for unload action"
            return self._unload_skill(skills, name)
        
        elif action == "active":
            return self._active_skills(skills)
        
        elif action == "show":
            if not name:
                return "Error: 'name' parameter required for show action"
            return self._show_skill(skills, name)
        
        elif action == "resources":
            if not name:
                return "Error: 'name' parameter required for resources action"
            return self._list_resources(skills, name)
        
        elif action == "read_resource":
            if not name:
                return "Error: 'name' parameter required for read_resource action"
            if not resource:
                return "Error: 'resource' parameter required for read_resource action"
            return self._read_resource(skills, name, resource)
        
        return f"Error: Unknown action '{action}'"
    
    def _list_skills(self, skills) -> str:
        """List all discovered skills"""
        skill_list = skills.list()
        
        if not skill_list:
            return "No skills found.\n\nTo add skills, create SKILL.md files in:\n- .codesm/skills/\n- skills/"
        
        lines = ["# Available Skills", ""]
        
        for s in skill_list:
            status = "✓ loaded" if s.is_active else ""
            lines.append(f"## {s.name} {status}")
            
            if s.description:
                lines.append(f"{s.description}")
            
            if s.triggers:
                lines.append(f"Triggers: {', '.join(s.triggers)}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _load_skill(self, skills, name: str) -> str:
        """Load a skill"""
        if skills.is_active(name):
            return f"Skill '{name}' is already loaded"
        
        skill = skills.load(name)
        if not skill:
            available = [s.name for s in skills.list()]
            return f"Skill '{name}' not found. Available: {', '.join(available)}"
        
        return f"✓ Loaded skill: {name}\n\n{skill.description or 'No description'}"
    
    def _unload_skill(self, skills, name: str) -> str:
        """Unload a skill"""
        if skills.unload(name):
            return f"✓ Unloaded skill: {name}"
        return f"Skill '{name}' is not currently loaded"
    
    def _active_skills(self, skills) -> str:
        """List active skills"""
        active = skills.active()
        
        if not active:
            return "No skills currently loaded. Use `skill load <name>` to load one."
        
        lines = ["# Active Skills", ""]
        
        for s in active:
            lines.append(f"- **{s.name}**: {s.description or 'No description'}")
        
        return "\n".join(lines)
    
    def _show_skill(self, skills, name: str) -> str:
        """Show skill content without loading"""
        skill = skills.get(name)
        if not skill:
            return f"Skill '{name}' not found"
        
        lines = [
            f"# Skill: {skill.name}",
            "",
            f"**Description:** {skill.description or 'None'}",
            f"**Triggers:** {', '.join(skill.triggers) or 'None'}",
            f"**Path:** {skill.path}",
            "",
            "## Content",
            "",
            skill.content,
        ]
        
        return "\n".join(lines)
    
    def _list_resources(self, skills, name: str) -> str:
        """List skill resources"""
        skill = skills.get(name)
        if not skill:
            return f"Skill '{name}' not found"
        
        if not skill.resources:
            return f"Skill '{name}' has no resources"
        
        lines = [f"# Resources for {name}", ""]
        
        for res in skill.resources:
            lines.append(f"- {res}")
        
        return "\n".join(lines)
    
    def _read_resource(self, skills, name: str, resource: str) -> str:
        """Read a skill resource file"""
        resource_path = skills.get_resource_path(name, resource)
        
        if not resource_path:
            skill = skills.get(name)
            if not skill:
                return f"Skill '{name}' not found"
            return f"Resource '{resource}' not found in skill '{name}'"
        
        try:
            content = resource_path.read_text(encoding="utf-8")
            return f"# {resource}\n\n```\n{content}\n```"
        except Exception as e:
            return f"Error reading resource: {e}"
