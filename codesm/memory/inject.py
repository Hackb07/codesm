"""Prompt injection for memories"""

from .models import MemoryItem


def render_memories_for_prompt(memories: list[MemoryItem]) -> str:
    if not memories:
        return ""

    lines = ["Relevant memories (from previous sessions):"]
    for memory in memories:
        type_label = memory.type.capitalize()
        lines.append(f"- {type_label}: {memory.text}")

    return "\n".join(lines)
