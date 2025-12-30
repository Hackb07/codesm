"""Theme system for codesm TUI"""

from textual.theme import Theme

CODESM_DARK = Theme(
    name="codesm-dark",
    primary="#5c6370",
    secondary="#61afef",
    accent="#e5c07b",
    foreground="#abb2bf",
    background="#1e1e2e",
    surface="#282c34",
    panel="#21252b",
    success="#98c379",
    warning="#e5c07b",
    error="#e06c75",
    dark=True,
    variables={
        "modal-bg": "#2d2d3d",
        "highlight": "#e5a07b",
        "muted": "#5c6370",
        "input-bg": "#3d3d4d",
        "border-color": "#5c6370",
    },
)

CODESM_LIGHT = Theme(
    name="codesm-light",
    primary="#383a42",
    secondary="#4078f2",
    accent="#c18401",
    foreground="#383a42",
    background="#fafafa",
    surface="#f0f0f0",
    panel="#e5e5e5",
    success="#50a14f",
    warning="#c18401",
    error="#e45649",
    dark=False,
    variables={
        "modal-bg": "#ffffff",
        "highlight": "#e5a07b",
        "muted": "#a0a1a7",
        "input-bg": "#ffffff",
        "border-color": "#d4d4d4",
    },
)

CODESM_OCEAN = Theme(
    name="codesm-ocean",
    primary="#8fa1b3",
    secondary="#96b5b4",
    accent="#ebcb8b",
    foreground="#c0c5ce",
    background="#1b2b34",
    surface="#243238",
    panel="#1b2b34",
    success="#99c794",
    warning="#ebcb8b",
    error="#ec5f67",
    dark=True,
    variables={
        "modal-bg": "#2b3b44",
        "highlight": "#f99157",
        "muted": "#65737e",
        "input-bg": "#343d46",
        "border-color": "#65737e",
    },
)

CODESM_DRACULA = Theme(
    name="codesm-dracula",
    primary="#6272a4",
    secondary="#8be9fd",
    accent="#ffb86c",
    foreground="#f8f8f2",
    background="#1e1f29",
    surface="#282a36",
    panel="#21222c",
    success="#50fa7b",
    warning="#ffb86c",
    error="#ff5555",
    dark=True,
    variables={
        "modal-bg": "#2d2f3d",
        "highlight": "#ff79c6",
        "muted": "#6272a4",
        "input-bg": "#383a4a",
        "border-color": "#6272a4",
    },
)

THEMES = {
    "dark": CODESM_DARK,
    "light": CODESM_LIGHT,
    "ocean": CODESM_OCEAN,
    "dracula": CODESM_DRACULA,
}

THEME_NAMES = list(THEMES.keys())


def get_next_theme(current: str) -> str:
    """Get the next theme in the rotation"""
    try:
        idx = THEME_NAMES.index(current)
        return THEME_NAMES[(idx + 1) % len(THEME_NAMES)]
    except ValueError:
        return THEME_NAMES[0]
