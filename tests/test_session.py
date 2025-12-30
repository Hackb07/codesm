"""Tests for session management"""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestSession:
    def test_create_session(self, temp_dir):
        from codesm.session.session import Session
        
        session = Session.create(temp_dir)
        
        assert session.id.startswith("session_")
        assert session.directory == temp_dir.resolve()
        assert session.messages == []
    
    def test_add_message(self, temp_dir):
        from codesm.session.session import Session
        
        session = Session.create(temp_dir)
        session.add_message(role="user", content="Hello")
        
        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"
    
    def test_add_message_with_metadata(self, temp_dir):
        from codesm.session.session import Session
        
        session = Session.create(temp_dir)
        session.add_message(
            role="tool",
            content="result",
            tool_call_id="call_123",
            name="read",
        )
        
        msg = session.messages[0]
        assert msg["role"] == "tool"
        assert msg["content"] == "result"
        assert msg["tool_call_id"] == "call_123"
        assert msg["name"] == "read"
    
    def test_get_messages_preserves_structure(self, temp_dir):
        from codesm.session.session import Session
        
        session = Session.create(temp_dir)
        session.add_message(role="user", content="Hello")
        session.add_message(
            role="tool",
            content="result",
            tool_call_id="call_123",
        )
        
        messages = session.get_messages()
        
        assert len(messages) == 2
        assert messages[1]["tool_call_id"] == "call_123"
    
    def test_get_messages_for_display(self, temp_dir):
        from codesm.session.session import Session
        
        session = Session.create(temp_dir)
        session.add_message(role="user", content="Hello")
        session.add_message(role="assistant", content="Hi there!")
        session.add_message(role="tool", content="result", tool_call_id="123")
        
        display_messages = session.get_messages_for_display()
        
        assert len(display_messages) == 2
        assert display_messages[0]["role"] == "user"
        assert display_messages[1]["role"] == "assistant"


class TestMessage:
    def test_message_to_dict(self):
        from codesm.session.message import Message
        
        msg = Message(
            role="user",
            content="Hello",
        )
        
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello"
    
    def test_message_with_tool_call(self):
        from codesm.session.message import Message
        
        msg = Message(
            role="assistant",
            content="Let me read that file",
            tool_calls=[{"id": "123", "name": "read", "arguments": {}}],
        )
        
        d = msg.to_dict()
        assert "tool_calls" in d
        assert len(d["tool_calls"]) == 1
