"""Find thread tool - search through past conversation threads"""

import logging
from typing import TYPE_CHECKING

from .base import Tool

if TYPE_CHECKING:
    from codesm.tool.registry import ToolRegistry

logger = logging.getLogger(__name__)


class FindThreadTool(Tool):
    """Search through past conversation threads using DSL query"""
    
    name = "find_thread"
    description = "Search past conversation threads by keywords, files, topics, or dates."
    
    def __init__(self, parent_tools: "ToolRegistry | None" = None):
        super().__init__()
        self._parent_tools = parent_tools
    
    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query with DSL syntax. Examples: 'auth file:src/auth.py', 'after:7d bugfix', 'topic:feature react'",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 20)",
                    "default": 20,
                },
            },
            "required": ["query"],
        }
    
    async def execute(self, args: dict, context: dict) -> str:
        from codesm.session.search import get_thread_search
        
        query = args.get("query", "")
        limit = args.get("limit", 20)
        
        if not query:
            return "Error: query is required"
        
        try:
            search = get_thread_search()
            results = search.search(query, limit=limit)
            
            if not results:
                return f"No threads found matching: {query}\n\nTry:\n- Different keywords\n- Broader date range (after:30d)\n- Checking topic: filter against available topics"
            
            # Format results
            output = [f"## Found {len(results)} thread(s) matching: `{query}`\n"]
            
            for i, result in enumerate(results, 1):
                # Format date
                date_str = result.updated_at.strftime("%Y-%m-%d %H:%M")
                
                # Format topics if available
                topics_str = ""
                if result.topics:
                    topics_str = f" • {result.topics.primary}"
                    if result.topics.secondary:
                        topics_str += f", {', '.join(result.topics.secondary[:2])}"
                
                output.append(
                    f"### {i}. {result.title}\n"
                    f"**ID:** `{result.session_id}`\n"
                    f"**Updated:** {date_str}{topics_str}\n"
                    f"**Snippet:** {result.snippet}\n"
                )
            
            output.append("\n---\nUse `read_thread` tool with a thread ID to extract specific context.")
            
            return "\n".join(output)
            
        except Exception as e:
            logger.exception("Thread search failed")
            return f"Error searching threads: {e}"
