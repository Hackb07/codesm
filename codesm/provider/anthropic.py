"""Anthropic provider implementation with OAuth and API key support"""

from typing import AsyncIterator
import json
import httpx

from .base import Provider, StreamChunk
from codesm.auth import ClaudeOAuth


class AnthropicProvider(Provider):
    """Provider for Anthropic Claude models with OAuth support"""
    
    API_URL = "https://api.anthropic.com/v1/messages"
    CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    
    def __init__(self, model: str):
        self.model = model
        self.oauth = ClaudeOAuth()
    
    async def _get_headers(self) -> dict:
        """Get headers for API request, handling OAuth vs API key"""
        creds = self.oauth.get_credentials()
        
        if not creds:
            # No credentials - try environment variable as fallback
            import os
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if api_key:
                return {
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "claude-code-20250219,interleaved-thinking-2025-05-14,fine-grained-tool-streaming-2025-05-14",
                }
            raise ValueError("No Anthropic credentials found. Run /connect to authenticate.")
        
        if creds.get("auth_type") == "api_key":
            return {
                "Content-Type": "application/json",
                "x-api-key": creds["api_key"],
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "claude-code-20250219,interleaved-thinking-2025-05-14,fine-grained-tool-streaming-2025-05-14",
            }
        
        elif creds.get("auth_type") == "oauth":
            # Check if token is expired and refresh if needed
            if self.oauth.is_token_expired():
                refresh_token = creds.get("refresh_token")
                if refresh_token:
                    result = await self.oauth.refresh_token(refresh_token)
                    if not result["success"]:
                        raise ValueError(f"Failed to refresh OAuth token: {result.get('error')}")
                    creds = self.oauth.get_credentials()
                else:
                    raise ValueError("OAuth token expired and no refresh token available")
            
            access_token = creds.get("access_token")
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "oauth-2025-04-20,claude-code-20250219,interleaved-thinking-2025-05-14,fine-grained-tool-streaming-2025-05-14",
            }
        
        raise ValueError("Invalid credential type")
    
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
        """Stream a response from Claude using raw HTTP with OAuth support"""
        
        headers = await self._get_headers()
        anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)
        
        # Build request body
        body = {
            "model": self.model,
            "max_tokens": 8192,
            "system": system,
            "messages": anthropic_messages,
            "stream": True,
        }
        
        if anthropic_tools:
            body["tools"] = anthropic_tools
        
        # Track current tool use block
        current_tool_id = None
        current_tool_name = None
        current_tool_input = ""
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                self.API_URL,
                headers=headers,
                json=body,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    try:
                        error_json = json.loads(error_text)
                        error_msg = error_json.get("error", {}).get("message", str(error_json))
                    except:
                        error_msg = error_text.decode()[:500]
                    raise ValueError(f"API error ({response.status_code}): {error_msg}")
                
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    
                    event_type = event.get("type")
                    
                    if event_type == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            current_tool_id = block.get("id")
                            current_tool_name = block.get("name")
                            current_tool_input = ""
                    
                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield StreamChunk(type="text", content=delta.get("text", ""))
                        elif delta.get("type") == "input_json_delta":
                            current_tool_input += delta.get("partial_json", "")
                    
                    elif event_type == "content_block_stop":
                        if current_tool_id and current_tool_name:
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
                    
                    elif event_type == "error":
                        error = event.get("error", {})
                        raise ValueError(f"Stream error: {error.get('message', str(error))}")
