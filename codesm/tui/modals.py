"""Modal dialogs for codesm TUI"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Input, Label
from textual.binding import Binding
from textual import events


MODELS_BY_PROVIDER = {
    "Recent": [
        {"id": "anthropic/claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "Anthropic"},
    ],
    "Anthropic": [
        {"id": "anthropic/claude-haiku-3", "name": "Claude Haiku 3", "provider": "Anthropic"},
        {"id": "anthropic/claude-haiku-3.5", "name": "Claude Haiku 3.5", "provider": "Anthropic"},
        {"id": "anthropic/claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "provider": "Anthropic"},
        {"id": "anthropic/claude-opus-4", "name": "Claude Opus 4", "provider": "Anthropic"},
    ],
    "OpenAI": [
        {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
        {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
        {"id": "openai/gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "OpenAI"},
        {"id": "openai/o1", "name": "O1", "provider": "OpenAI"},
        {"id": "openai/o1-mini", "name": "O1 Mini", "provider": "OpenAI"},
    ],
    "Google": [
        {"id": "google/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "Google"},
        {"id": "google/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "Google"},
    ],
}

PROVIDERS = {
    "Popular": [
        {"id": "anthropic", "name": "Anthropic", "hint": "Claude Max or API key"},
        {"id": "github-copilot", "name": "GitHub Copilot", "hint": ""},
        {"id": "openai", "name": "OpenAI", "hint": ""},
        {"id": "google", "name": "Google", "hint": ""},
        {"id": "openrouter", "name": "OpenRouter", "hint": ""},
    ],
    "Other": [
        {"id": "ollama", "name": "Ollama", "hint": "Local models"},
        {"id": "groq", "name": "Groq", "hint": "Fast inference"},
        {"id": "together", "name": "Together AI", "hint": ""},
        {"id": "fireworks", "name": "Fireworks AI", "hint": ""},
        {"id": "deepseek", "name": "DeepSeek", "hint": ""},
    ],
}


class ModalListItem(Static):
    """A selectable item in a modal list"""

    def __init__(self, item_id: str, label: str, hint: str = "", **kwargs):
        super().__init__(**kwargs)
        self.item_id = item_id
        self.label = label
        self.hint = hint
        self._selected = False

    def compose(self) -> ComposeResult:
        if self.hint:
            yield Static(f"  {self.label} [dim]{self.hint}[/]", classes="item-content")
        else:
            yield Static(f"  {self.label}", classes="item-content")

    def set_selected(self, selected: bool):
        self._selected = selected
        self.set_class(selected, "-selected")


class ModelSelectModal(ModalScreen):
    """Modal for selecting a model"""

    CSS = """
    ModelSelectModal {
        align: center middle;
    }

    #modal-container {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #modal-header {
        height: 3;
        width: 100%;
    }

    #modal-title {
        text-style: bold;
    }

    #esc-hint {
        dock: right;
        color: $text-muted;
    }

    #search-input {
        margin: 1 0;
        border: tall $primary;
        background: $panel;
    }

    #search-input:focus {
        border: tall $accent;
    }

    #model-list {
        height: auto;
        max-height: 20;
        padding: 0;
    }

    .group-header {
        color: $accent;
        text-style: bold;
        padding: 1 0 0 0;
    }

    ModalListItem {
        height: 1;
        padding: 0;
    }

    ModalListItem.-selected {
        background: #e5a07b;
        color: #1e1e2e;
    }

    ModalListItem.-selected .item-content {
        color: #1e1e2e;
        text-style: bold;
    }

    #modal-footer {
        height: 2;
        padding: 1 0 0 0;
        color: $text-muted;
    }

    #modal-footer Static {
        margin-right: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    def __init__(self, current_model: str = ""):
        super().__init__()
        self.current_model = current_model
        self.selected_index = 0
        self.visible_items: list[ModalListItem] = []
        self.search_query = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            with Horizontal(id="modal-header"):
                yield Static("Select model", id="modal-title")
                yield Static("esc", id="esc-hint")
            yield Input(placeholder="Search", id="search-input")
            yield VerticalScroll(id="model-list")
            with Horizontal(id="modal-footer"):
                yield Static("[bold]Connect provider[/] ctrl+a")
                yield Static("[bold]Favorite[/] ctrl+f")

    def on_mount(self):
        self._build_list()
        self.query_one("#search-input", Input).focus()

    def _build_list(self, filter_text: str = ""):
        container = self.query_one("#model-list", VerticalScroll)
        container.remove_children()
        self.visible_items = []

        filter_lower = filter_text.lower()

        for group_name, models in MODELS_BY_PROVIDER.items():
            filtered_models = [
                m for m in models
                if filter_lower in m["name"].lower() or filter_lower in m.get("provider", "").lower()
            ] if filter_text else models

            if not filtered_models:
                continue

            container.mount(Static(group_name, classes="group-header"))

            for model in filtered_models:
                hint = model.get("provider", "")
                item = ModalListItem(model["id"], model["name"], hint)
                container.mount(item)
                self.visible_items.append(item)

        if self.visible_items:
            self.selected_index = 0
            self.visible_items[0].set_selected(True)

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "search-input":
            self.search_query = event.value
            self._build_list(event.value)

    def action_move_up(self):
        if not self.visible_items:
            return
        self.visible_items[self.selected_index].set_selected(False)
        self.selected_index = (self.selected_index - 1) % len(self.visible_items)
        self.visible_items[self.selected_index].set_selected(True)
        self.visible_items[self.selected_index].scroll_visible()

    def action_move_down(self):
        if not self.visible_items:
            return
        self.visible_items[self.selected_index].set_selected(False)
        self.selected_index = (self.selected_index + 1) % len(self.visible_items)
        self.visible_items[self.selected_index].set_selected(True)
        self.visible_items[self.selected_index].scroll_visible()

    def action_select(self):
        if self.visible_items:
            selected = self.visible_items[self.selected_index]
            self.dismiss(selected.item_id)

    def action_dismiss(self):
        self.dismiss(None)


class ProviderConnectModal(ModalScreen):
    """Modal for connecting a provider"""

    CSS = """
    ProviderConnectModal {
        align: center middle;
    }

    #modal-container {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #modal-header {
        height: 3;
        width: 100%;
    }

    #modal-title {
        text-style: bold;
    }

    #esc-hint {
        dock: right;
        color: $text-muted;
    }

    #search-input {
        margin: 1 0;
        border: tall $primary;
        background: $panel;
    }

    #search-input:focus {
        border: tall $accent;
    }

    #provider-list {
        height: auto;
        max-height: 20;
        padding: 0;
    }

    .group-header {
        color: $accent;
        text-style: bold;
        padding: 1 0 0 0;
    }

    ModalListItem {
        height: 1;
        padding: 0;
    }

    ModalListItem.-selected {
        background: #e5a07b;
        color: #1e1e2e;
    }

    ModalListItem.-selected .item-content {
        color: #1e1e2e;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.selected_index = 0
        self.visible_items: list[ModalListItem] = []
        self.search_query = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            with Horizontal(id="modal-header"):
                yield Static("Connect a provider", id="modal-title")
                yield Static("esc", id="esc-hint")
            yield Input(placeholder="Search", id="search-input")
            yield VerticalScroll(id="provider-list")

    def on_mount(self):
        self._build_list()
        self.query_one("#search-input", Input).focus()

    def _build_list(self, filter_text: str = ""):
        container = self.query_one("#provider-list", VerticalScroll)
        container.remove_children()
        self.visible_items = []

        filter_lower = filter_text.lower()

        for group_name, providers in PROVIDERS.items():
            filtered_providers = [
                p for p in providers
                if filter_lower in p["name"].lower() or filter_lower in p.get("hint", "").lower()
            ] if filter_text else providers

            if not filtered_providers:
                continue

            container.mount(Static(group_name, classes="group-header"))

            for provider in filtered_providers:
                hint = provider.get("hint", "")
                item = ModalListItem(provider["id"], provider["name"], hint)
                container.mount(item)
                self.visible_items.append(item)

        if self.visible_items:
            self.selected_index = 0
            self.visible_items[0].set_selected(True)

    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "search-input":
            self.search_query = event.value
            self._build_list(event.value)

    def action_move_up(self):
        if not self.visible_items:
            return
        self.visible_items[self.selected_index].set_selected(False)
        self.selected_index = (self.selected_index - 1) % len(self.visible_items)
        self.visible_items[self.selected_index].set_selected(True)
        self.visible_items[self.selected_index].scroll_visible()

    def action_move_down(self):
        if not self.visible_items:
            return
        self.visible_items[self.selected_index].set_selected(False)
        self.selected_index = (self.selected_index + 1) % len(self.visible_items)
        self.visible_items[self.selected_index].set_selected(True)
        self.visible_items[self.selected_index].scroll_visible()

    def action_select(self):
        if self.visible_items:
            selected = self.visible_items[self.selected_index]
            self.dismiss(selected.item_id)

    def action_dismiss(self):
        self.dismiss(None)
