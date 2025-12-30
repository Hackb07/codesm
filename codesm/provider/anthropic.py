"""Anthropic provider implementation with full tool support"""

from typing import AsyncIterator
import json
import anthropic

from .base import Provider, StreamChunk


class AnthropicProvider(Provider):
    """Provider for Anthropic Claude models"""
    
    def __init__(self, model: str):
        self.model = model
        self.client = anthropic.AsyncAnthropic()
    
    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert internal message format to Anthropic format"""
        result = []
        pending_tool_results = []
        
        for msg in messages:
            role = msg.get("role")
            
            if role == "user":
                # Flush any pending tool results first
                if pending_tool_results:
                    result.append({
                        "role": "user",
                        "content": pending_tool_results,
                    })
                    pending_tool_results = []
                
                result.append({
                    "role": "user",
                    "content": msg.get("content", ""),
                })
            
            elif role == "assistant":
                content = []
                if msg.get("content"):
                    content.append({
                        "type": "text",
                        "text": msg["content"],
                    })
                
                # Add tool use blocks
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        args = tc.get("function", {}).get("arguments", "{}")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        
                        content.append({
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": tc.get("function", {}).get("name", ""),
                            "input": args,
                        })
                
                if content:
                    result.append({
                        "role": "assistant",
                        "content": content,
                    })
            
            elif role == "tool":
                # Collect tool results to send as user message
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", ""),
                })
        
        # Flush remaining tool results
        if pending_tool_results:
            result.append({
                "role": "user",
                "content": pending_tool_results,
            })
        
        return result
    
    def _convert_tools(self, tools: list[dict] | None) -> list[dict] | None:
        """Convert internal tool format to Anthropic format"""
        if not tools:
            return None
        
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in tools
        ]
    
    async def stream(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from Claude"""
        
        anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)
        
        # Build request kwargs
        kwargs = {
            "model": self.model,
            "max_tokens": 8192,
            "system": system,
            "messages": anthropic_messages,
        }
        
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
        
        # Track current tool use block
        current_tool_id = None
        current_tool_name = None
        current_tool_input = ""
        
        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "text":
                        pass  # Text will come in deltas
                    elif block.type == "tool_use":
                        current_tool_id = block.id
                        current_tool_name = block.name
                        current_tool_input = ""
                
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if hasattr(delta, "text"):
                        yield StreamChunk(type="text", content=delta.text)
                    elif hasattr(delta, "partial_json"):
                        current_tool_input += delta.partial_json
                
                elif event.type == "content_block_stop":
                    if current_tool_id and current_tool_name:
                        # Parse accumulated JSON
                        try:
                            args = json.loads(current_tool_input) if current_tool_input else {}
                        except json.JSONDecodeError:
                            args = {}
                        
                        yield StreamChunk(
                            type="tool_call",
                            id=current_tool_id,
                            name=current_tool_name,
                            args=args,
                        )
                        
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_input = ""
