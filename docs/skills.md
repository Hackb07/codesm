# Skills System

Skills are markdown files that inject specialized instructions and workflows into the agent's context. They allow you to define custom agent behaviors for specific tasks.

## Quick Start

1. Create a skill directory:
```bash
mkdir -p .codesm/skills/my-skill
```

2. Create `SKILL.md` in that directory:
```markdown
---
name: my-skill
description: Does something specific
triggers:
  - "(?i)keyword"
---

# My Skill

Instructions for the agent when this skill is active...
```

3. The skill will auto-load when you send a message matching the trigger pattern, or you can load it manually:
```
Use the skill tool to load "my-skill"
```

## Skill File Format

Skills are defined in `SKILL.md` files with YAML frontmatter:

```markdown
---
name: skill-name           # Required: unique identifier
description: What it does  # Optional: shown in listings
triggers:                  # Optional: regex patterns for auto-loading
  - "(?i)pattern1"
  - "(?i)pattern2"
resources:                 # Optional: list bundled files
  - templates/example.txt
---

# Skill Content

Markdown content that gets injected into the agent's system prompt
when the skill is loaded.
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes* | Skill identifier (*falls back to directory name) |
| `description` | No | Brief description shown in listings |
| `triggers` | No | Regex patterns that auto-load the skill |
| `resources` | No | Bundled files (auto-discovered if not specified) |

## Skill Discovery

Skills are discovered from these directories (in order of precedence):

1. `{workspace}/.codesm/skills/**/SKILL.md`
2. `{workspace}/skills/**/SKILL.md`

Workspace `skills/` directory takes precedence over `.codesm/skills/` for naming conflicts.

## Triggers

Triggers are regex patterns (Python `re`) matched against user messages. When a pattern matches, the skill is auto-loaded.

```yaml
triggers:
  - "(?i)review"           # Case-insensitive match for "review"
  - "(?i)test.*coverage"   # Match "test" followed by "coverage"
  - "^/deploy"             # Match messages starting with "/deploy"
```

Skills only auto-load once per session. To re-trigger, unload the skill first.

## Resources

Skills can bundle additional files (templates, scripts, configs) alongside `SKILL.md`:

```
.codesm/skills/api-design/
├── SKILL.md
├── templates/
│   └── openapi.yaml
└── scripts/
    └── validate.sh
```

The agent can access these via the skill tool:
```json
{"action": "read_resource", "name": "api-design", "resource": "templates/openapi.yaml"}
```

## Skill Tool

The `skill` tool allows the agent to manage skills:

| Action | Description |
|--------|-------------|
| `list` | Show all available skills |
| `load` | Load a skill by name |
| `unload` | Remove a skill from context |
| `active` | Show currently loaded skills |
| `show` | Display skill content without loading |
| `resources` | List skill's bundled files |
| `read_resource` | Read a specific resource file |

## Examples

### Code Review Skill

```markdown
---
name: code-review
description: Thorough code review with security focus
triggers:
  - "(?i)review"
  - "(?i)check.*code"
---

# Code Review

When reviewing code, check for:

## Security
- SQL injection
- XSS vulnerabilities
- Hardcoded secrets

## Performance
- N+1 queries
- Memory leaks
```

### Debugging Skill

```markdown
---
name: debugging
description: Systematic debugging approach
triggers:
  - "(?i)debug"
  - "(?i)not working"
  - "(?i)error"
---

# Debugging

1. Reproduce the issue
2. Read error messages carefully
3. Check recent changes (git log)
4. Form hypothesis
5. Test with minimal case
6. Verify fix
```

## Best Practices

1. **Keep skills focused** - One skill per task type
2. **Use descriptive triggers** - Be specific to avoid false matches
3. **Include examples** - Show the agent what good output looks like
4. **Bundle resources** - Templates and scripts make skills more useful
5. **Document prerequisites** - Note any required tools or setup
