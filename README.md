# codesm

An AI coding agent built with Python + Rust. Features a TUI interface, multi-provider support (Anthropic Claude, OpenAI GPT), and a powerful tool system for reading, writing, and executing code.

## Features

- **Multi-Provider Support**: Works with Anthropic Claude and OpenAI GPT models
- **ReAct Loop**: Implements reasoning + acting pattern for complex multi-step tasks
- **Rich Tool System**: Read, write, edit files, run bash commands, search with grep/glob
- **Terminal UI**: Beautiful TUI built with Textual
- **Rust Core**: Performance-critical operations (diffing, indexing) powered by Rust via PyO3
- **Session Management**: Persistent conversation history

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Rust toolchain (for building the core module)
- API keys for Anthropic and/or OpenAI

### Install from source

```bash
# Clone the repository
cd codesm

# Install dependencies
uv sync

# Build Rust core (optional, for better performance)
cd core
maturin develop --release
cd ..

# Set API keys
export ANTHROPIC_API_KEY="your-key"
# or
export OPENAI_API_KEY="your-key"
```

## Usage

### TUI Mode (Interactive)

```bash
# Start in current directory with default model (Claude)
codesm run

# Start in a specific directory
codesm run /path/to/project

# Use a specific model
codesm run --model openai/gpt-4o
codesm run --model anthropic/claude-sonnet-4-20250514
```

### Single Message Mode

```bash
# Send a single message and get response
codesm chat "What files are in this directory?"

# With specific directory and model
codesm chat "Fix the bug in main.py" --dir ./myproject --model openai/gpt-4o
```

### HTTP API Mode

```bash
# Start the API server
codesm serve --port 4096

# Send requests
curl -X POST http://localhost:4096/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List all Python files"}'
```

## Available Tools

| Tool | Description |
|------|-------------|
| `read` | Read file contents with line numbers |
| `write` | Create or overwrite files |
| `edit` | Edit files by replacing content |
| `bash` | Execute shell commands |
| `grep` | Search for patterns using ripgrep |
| `glob` | Find files matching patterns |
| `web` | Fetch content from URLs |

## Configuration

Create a `codesm.json` in your project or home directory:

```json
{
  "model": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "temperature": 0.7,
    "max_tokens": 8192
  },
  "tools": {
    "enabled": ["read", "write", "edit", "bash", "grep", "glob", "web"]
  }
}
```

## Project Structure

```
codesm/
├── core/                   # Rust core (PyO3)
│   ├── src/
│   │   ├── lib.rs         # Module exports
│   │   ├── diff.rs        # Fast diffing
│   │   ├── sandbox.rs     # Secure execution
│   │   ├── index.rs       # File indexing
│   │   └── platform.rs    # Cross-platform utils
│   └── Cargo.toml
├── codesm/                 # Python package
│   ├── agent/             # Agent orchestration
│   │   ├── agent.py       # Main agent class
│   │   ├── loop.py        # ReAct loop
│   │   └── prompt.py      # System prompts
│   ├── provider/          # LLM providers
│   │   ├── anthropic.py   # Claude provider
│   │   └── openai.py      # GPT provider
│   ├── tool/              # Tool implementations
│   ├── session/           # Session management
│   ├── tui/               # Terminal UI
│   └── cli.py             # CLI entry point
├── tests/                  # Test suite
├── prompts/               # Prompt templates
└── pyproject.toml
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
pytest

# Run with verbose output
codesm run --model anthropic/claude-sonnet-4-20250514

# Build Rust core in debug mode
cd core && maturin develop
```

## Keyboard Shortcuts (TUI)

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Ctrl+N` | New session |
| `Ctrl+L` | Clear display |
| `Ctrl+C` | Quit |

## License

MIT

## Acknowledgments

Inspired by [OpenCode](https://github.com/sst/opencode) and built to explore Python + Rust patterns for AI coding agents.
