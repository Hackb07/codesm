"""Terminal UI for codesm"""

from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Center
from textual.widgets import Footer, Input, Static, RichLog
from textual.binding import Binding

from .themes import THEMES, get_next_theme
from .modals import ModelSelectModal, ProviderConnectModal, AuthMethodModal, APIKeyInputModal
from .command_palette import CommandPaletteModal
from codesm.auth import ClaudeOAuth

LOGO = """
 ██████╗ ██████╗ ██████╗ ███████╗███████╗███╗   ███╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔════╝████╗ ████║
██║     ██║   ██║██║  ██║█████╗  ███████╗██╔████╔██║
██║     ██║   ██║██║  ██║██╔══╝  ╚════██║██║╚██╔╝██║
╚██████╗╚██████╔╝██████╔╝███████╗███████║██║ ╚═╝ ██║
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝     ╚═╝
"""

VERSION = "0.1.0"


class CodesmApp(App):
    """Main TUI application"""

    CSS = """
    Screen {
        background: $background;
    }

    #main-container {
        width: 100%;
        height: 100%;
    }

    #welcome-view {
        width: 100%;
        height: 100%;
        align: center middle;
    }

    #logo {
        text-align: center;
        color: $foreground;
        width: auto;
        text-style: bold;
    }

    #version {
        text-align: center;
        color: $text-muted;
        padding-bottom: 2;
    }

    #input-container {
        width: 80;
        height: auto;
        align: center middle;
        border-left: tall $primary;
        background: $surface;
        padding: 0 1;
    }

    #message-input {
        width: 100%;
        border: none;
        background: $surface;
        color: $foreground;
        padding: 0 1;
    }

    #message-input:focus {
        border: none;
    }

    #model-indicator {
        color: $secondary;
        text-style: bold;
        padding: 0 1;
    }

    #hints {
        text-align: center;
        color: $text-muted;
        padding-top: 2;
    }

    .hint-key {
        text-style: bold;
        color: $foreground;
    }

    #chat-view {
        width: 100%;
        height: 100%;
        display: none;
    }

    #chat-container {
        height: 1fr;
        background: $background;
    }

    #messages {
        height: 100%;
        padding: 1 2;
        background: $background;
    }

    #chat-input-section {
        height: auto;
        dock: bottom;
        background: $surface;
        border-top: tall $primary;
        padding: 1;
    }

    #chat-input-container {
        width: 100%;
        border-left: tall $primary;
        background: $surface;
        padding: 0 1;
    }

    #chat-message-input {
        width: 100%;
        border: none;
        background: $surface;
        color: $foreground;
    }

    #chat-model-indicator {
        color: $secondary;
        padding: 0 1;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }

    .user-message {
        color: $secondary;
        text-style: bold;
        margin: 1 0;
    }

    .assistant-message {
        color: $success;
        margin: 1 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+n", "new_session", "New Session", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("ctrl+a", "connect_provider", "Connect Provider", show=True),
        Binding("ctrl+t", "toggle_theme", "Theme", show=True),
        Binding("ctrl+p", "show_command_palette", "Commands", show=True),
    ]

    def __init__(self, directory: Path, model: str):
        super().__init__()
        self.directory = directory
        self.model = model
        self.agent = None
        self.in_chat = False
        self._theme_name = "dark"
        self._showing_palette = False
        self._claude_oauth = ClaudeOAuth()

    def compose(self) -> ComposeResult:
        with Container(id="main-container"):
            with Vertical(id="welcome-view"):
                yield Center(Static(LOGO, id="logo"))
                yield Center(Static(VERSION, id="version"))
                with Center():
                    with Vertical(id="input-container"):
                        yield Input(
                            placeholder="Build anything...",
                            id="message-input"
                        )
                        yield Static(f"Build  {self._short_model_name()}", id="model-indicator")
                yield Center(
                    Static(
                        "[bold]tab[/] switch agent  [bold]ctrl+p[/] commands",
                        id="hints"
                    )
                )

            with Vertical(id="chat-view"):
                with Container(id="chat-container"):
                    yield RichLog(id="messages", wrap=True, highlight=True, markup=True)
                with Vertical(id="chat-input-section"):
                    with Horizontal(id="chat-input-container"):
                        yield Input(
                            placeholder="Continue the conversation...",
                            id="chat-message-input"
                        )
                    yield Static(f"{self._short_model_name()}", id="chat-model-indicator")

            yield Static(f"~/{self.directory}", id="status-bar")
        yield Footer()

    def _short_model_name(self) -> str:
        """Get short display name for current model"""
        if "/" in self.model:
            _, model_id = self.model.split("/", 1)
            return model_id
        return self.model

    def _get_active_input(self) -> Input:
        """Get the currently active input"""
        if self.in_chat:
            return self.query_one("#chat-message-input", Input)
        return self.query_one("#message-input", Input)

    async def on_mount(self):
        """Initialize when app mounts"""
        for theme in THEMES.values():
            self.register_theme(theme)
        self.theme = "codesm-dark"

        from codesm.agent.agent import Agent
        self.agent = Agent(directory=self.directory, model=self.model)

        input_widget = self.query_one("#message-input", Input)
        input_widget.focus()

    def on_input_changed(self, event: Input.Changed):
        """Handle input text changes - show command palette when / is typed"""
        if self._showing_palette:
            return

        text = event.value
        if text == "/":
            self._showing_palette = True
            event.input.value = ""
            self.push_screen(CommandPaletteModal("/"), self._on_palette_dismiss)

    def _on_palette_dismiss(self, result: str | None):
        """Handle command palette dismiss"""
        self._showing_palette = False
        if result:
            self.call_later(self._execute_command_sync, result)
        self._get_active_input().focus()

    def _execute_command_sync(self, cmd: str):
        """Execute command synchronously, scheduling async operations"""
        if cmd == "/models":
            self.push_screen(ModelSelectModal(self.model), self._on_model_selected)
        elif cmd == "/theme":
            self.action_toggle_theme()
        elif cmd == "/new":
            self.action_new_session()
        elif cmd == "/connect":
            self.push_screen(ProviderConnectModal(), self._on_provider_selected)
        elif cmd == "/help":
            self.notify("Commands: /init, /new, /models, /agents, /session, /status, /theme, /editor, /connect, /help")
        elif cmd == "/status":
            self.notify(f"Model: {self.model} | Dir: {self.directory}")
        elif cmd == "/init":
            self.notify("AGENTS.md initialization (coming soon)")
        elif cmd == "/agents":
            self.notify("Agent list (coming soon)")
        elif cmd == "/session":
            self.notify("Session list (coming soon)")
        elif cmd == "/editor":
            self.notify("Editor (coming soon)")
        else:
            self.notify(f"Unknown command: {cmd}")

    def _on_model_selected(self, result: str | None):
        """Handle model selection"""
        if result:
            if result == "__connect_provider__":
                self.push_screen(ProviderConnectModal(), self._on_provider_selected)
                return
            self.model = result
            self._update_model_display()
            if self.agent:
                self.agent.model = result
        self._get_active_input().focus()

    def _on_provider_selected(self, result: str | None):
        """Handle provider selection"""
        if result:
            if result == "anthropic":
                self.push_screen(AuthMethodModal("anthropic"), self._on_auth_method_selected)
            else:
                self.notify(f"Selected provider: {result} (coming soon)")
                self._get_active_input().focus()
        else:
            self._get_active_input().focus()

    def _on_auth_method_selected(self, result: str | None):
        """Handle auth method selection"""
        if result:
            if result == "manual-api-key":
                self.push_screen(APIKeyInputModal("anthropic"), self._on_api_key_entered)
            elif result == "create-api-key":
                import webbrowser
                webbrowser.open("https://console.anthropic.com/settings/keys")
                self.notify("Opening Anthropic console - copy your API key and use /connect again")
                self._get_active_input().focus()
        else:
            self._get_active_input().focus()

    def _on_api_key_entered(self, result: dict | None):
        """Handle API key entry"""
        if result:
            self._claude_oauth.save_api_key(result["api_key"])
            self.notify("API key saved! You can now use Anthropic models.")
            self._get_active_input().focus()
        else:
            self._get_active_input().focus()

    async def _execute_command(self, cmd: str):
        """Execute a slash command"""
        if cmd == "/models":
            await self._show_model_selector()
        elif cmd == "/theme":
            self.action_toggle_theme()
        elif cmd == "/new":
            self.action_new_session()
        elif cmd == "/connect":
            await self.action_connect_provider()
        elif cmd == "/help":
            self.notify("Commands: /init, /new, /models, /agents, /session, /status, /theme, /editor, /connect, /help")
        elif cmd == "/status":
            self.notify(f"Model: {self.model} | Dir: {self.directory}")
        elif cmd == "/init":
            self.notify("AGENTS.md initialization (coming soon)")
        elif cmd == "/agents":
            self.notify("Agent list (coming soon)")
        elif cmd == "/session":
            self.notify("Session list (coming soon)")
        elif cmd == "/editor":
            self.notify("Editor (coming soon)")
        else:
            self.notify(f"Unknown command: {cmd}")

    async def on_input_submitted(self, event: Input.Submitted):
        """Handle message submission"""
        message = event.value.strip()
        if not message:
            return

        if message.startswith("/"):
            event.input.value = ""
            self._execute_command_sync(message)
            return

        # Clear input immediately and save the message
        event.input.value = ""
        user_message = message

        # Switch to chat view if needed
        if not self.in_chat:
            self._switch_to_chat()

        # Schedule the actual chat handling after the UI has updated
        self.call_later(lambda: self._handle_chat_message(user_message))

    def _handle_chat_message(self, message: str):
        """Handle the chat message after UI is ready"""
        import asyncio
        asyncio.create_task(self._async_handle_chat(message))

    async def _async_handle_chat(self, message: str):
        """Async handler for chat messages"""
        input_widget = self.query_one("#chat-message-input", Input)
        input_widget.disabled = True

        messages_log = self.query_one("#messages", RichLog)
        
        # Show user message immediately
        messages_log.write(f"[bold cyan]You:[/bold cyan] {message}")
        messages_log.write("")
        messages_log.write("[dim]Thinking...[/dim]")

        try:
            response_text = ""
            async for chunk in self.agent.chat(message):
                if not response_text:
                    # First chunk - clear thinking message and show header
                    messages_log.clear()
                    messages_log.write(f"[bold cyan]You:[/bold cyan] {message}")
                    messages_log.write("")
                    messages_log.write("[bold green]Assistant:[/bold green]")
                response_text += chunk

            # Write the complete response
            if response_text:
                messages_log.write(response_text)
            else:
                messages_log.write("[yellow]No response received[/yellow]")

        except Exception as e:
            error_msg = str(e)
            if "No Anthropic credentials" in error_msg:
                messages_log.write("[bold red]Error:[/bold red] Not authenticated. Use /connect to authenticate with Anthropic.")
            else:
                messages_log.write(f"[bold red]Error:[/bold red] {error_msg}")

        finally:
            input_widget.disabled = False
            input_widget.focus()
            messages_log.write("")
            messages_log.write("[dim]───────────────────────────────────────[/dim]")

    def _switch_to_chat(self):
        """Switch from welcome view to chat view"""
        self.in_chat = True
        self.query_one("#welcome-view").styles.display = "none"
        self.query_one("#chat-view").styles.display = "block"
        self.query_one("#chat-message-input", Input).focus()

    def _switch_to_welcome(self):
        """Switch from chat view to welcome view"""
        self.in_chat = False
        self.query_one("#welcome-view").styles.display = "block"
        self.query_one("#chat-view").styles.display = "none"
        self.query_one("#message-input", Input).focus()

    async def _show_model_selector(self):
        """Show model selection modal"""
        result = await self.push_screen_wait(ModelSelectModal(self.model))
        if result:
            self.model = result
            self._update_model_display()
            if self.agent:
                self.agent.model = result

    def _update_model_display(self):
        """Update model display in UI"""
        short_name = self._short_model_name()
        self.query_one("#model-indicator", Static).update(f"Build  {short_name}")
        self.query_one("#chat-model-indicator", Static).update(short_name)

    def action_toggle_theme(self):
        """Toggle between themes"""
        self._theme_name = get_next_theme(self._theme_name)
        self.theme = f"codesm-{self._theme_name}"
        self.notify(f"Theme: {self._theme_name}")

    async def action_connect_provider(self):
        """Show connect provider modal"""
        result = await self.push_screen_wait(ProviderConnectModal())
        if result:
            self.notify(f"Selected provider: {result}")

    def action_new_session(self):
        """Create a new session"""
        from codesm.session.session import Session
        if self.agent:
            self.agent.session = Session.create(self.directory)
        if self.in_chat:
            messages = self.query_one("#messages", RichLog)
            messages.clear()
            messages.write("[bold green]New session started[/]")
        self._switch_to_welcome()
        self.notify("New session started")

    def action_clear(self):
        """Clear the message history display"""
        if self.in_chat:
            messages = self.query_one("#messages", RichLog)
            messages.clear()
            messages.write("[bold yellow]Display cleared[/]")

    def action_show_command_palette(self):
        """Show command palette via Ctrl+P"""
        self._showing_palette = True
        self.push_screen(CommandPaletteModal("/"), self._on_palette_dismiss)
