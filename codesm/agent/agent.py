"""Main agent - orchestrates LLM calls and tool execution"""

from pathlib import Path
from typing import AsyncIterator
from dataclasses import dataclass, field

from codesm.provider.base import get_provider, StreamChunk
from codesm.tool.registry import ToolRegistry
from codesm.session.session import Session
from codesm.agent.prompt import SYSTEM_PROMPT
from codesm.agent.loop import ReActLoop


@dataclass
class Agent:
    """AI coding agent that can read, write, and execute code"""
    
    directory: Path
    model: str
    session: Session | None = None
    max_iterations: int = 15
    
    def __post_init__(self):
        self.directory = Path(self.directory).resolve()
        self.session = Session.create(self.directory)
        self.tools = ToolRegistry()
        self.provider = get_provider(self.model)
        self.react_loop = ReActLoop(max_iterations=self.max_iterations)
    
    async def chat(self, message: str) -> AsyncIterator[str]:
        """Send a message and stream the response"""
        # Add user message to session
        self.session.add_message(role="user", content=message)
        
        # Get conversation history
        messages = self.session.get_messages()
        
        # Build context for tools
        context = {
            "session": self.session,
            "cwd": self.directory,
        }
        
        # Run ReAct loop
        full_response = ""
        async for chunk in self.react_loop.execute(
            provider=self.provider,
            system_prompt=SYSTEM_PROMPT.format(cwd=self.directory),
            messages=messages,
            tools=self.tools,
            context=context,
        ):
            if chunk.type == "text":
                full_response += chunk.content
                yield chunk.content
            elif chunk.type == "tool_call":
                # Yield tool call info for TUI display
                yield f"\n[Tool: {chunk.name}]\n"
            elif chunk.type == "tool_result":
                # Yield abbreviated tool result
                result_preview = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content
                yield f"[Result: {result_preview}]\n"
        
        # Save final assistant response
        if full_response:
            self.session.add_message(role="assistant", content=full_response)
    
    def new_session(self):
        """Start a new session"""
        self.session = Session.create(self.directory)
