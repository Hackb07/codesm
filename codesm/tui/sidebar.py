"""Sidebar for session management"""

from textual.widgets import ListView, ListItem, Label, Button
from textual.containers import Container


class SessionListItem(ListItem):
    """A session item in the sidebar"""

    def __init__(self, session_id: str, title: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self.title = title

    def compose(self):
        yield Label(self.title)


class Sidebar(Container):
    """Sidebar showing session list"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions = []

    def compose(self):
        yield Label("Sessions", classes="sidebar-title")
        yield Button("+ New Session", id="new-session")
        yield ListView(id="session-list")

    def add_session(self, session_id: str, title: str):
        """Add a session to the list"""
        item = SessionListItem(session_id, title)
        list_view = self.query_one("#session-list", ListView)
        list_view.append(item)
        self.sessions.append({"id": session_id, "title": title})

    def clear_sessions(self):
        """Clear all sessions"""
        list_view = self.query_one("#session-list", ListView)
        list_view.clear()
        self.sessions.clear()
