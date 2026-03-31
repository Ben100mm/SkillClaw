# Skill-Aware Router — Agent Instructions

## Build & Run

```bash
# Install dependencies
uv sync

# Run the MCP server (stdio transport — for Cursor / Claude Desktop)
uv run fastmcp run main.py:mcp

# Run the server on HTTP (for remote clients)
uv run fastmcp run main.py:mcp --transport http --port 8000

# Run directly
uv run python main.py
```

## Test

```bash
uv run pytest tests/ -v
```

## Environment Variables

The server requires two API keys set as environment variables:

- `ANTHROPIC_API_KEY` — for Claude Sonnet execution
- `GOOGLE_API_KEY` — for Gemini Flash (router) and Gemini Pro (research execution)

Copy `.env.example` to `.env` and fill in your keys.

## Architecture

- **FastMCP 3.0** exposes three tools: `list_skills`, `execute_smart_task`, `reload_skills`.
- **Skill Registry** (`SkillRegistry`) reads `.md` files from `skills_library/`, parses YAML frontmatter, and builds an in-memory capability map.
- **Router** uses Gemini 1.5 Flash to match a user prompt against skill descriptions (fast + cheap).
- **Selector** inspects skill tags to pick the execution model:
  - Tags `coding`, `logic`, `code`, `review`, `debug`, `refactor` → Claude Sonnet
  - Tags `research`, `data`, `analysis`, `search`, `report` → Gemini 1.5 Pro
- **Executor** injects the skill body as a system prompt and calls the selected model.

## Key Patterns

- Always use `@mcp.tool` for new routing logic or exposing new capabilities.
- Skills are plain Markdown files with YAML frontmatter — no code changes needed to add a new skill.
- Use Gemini Flash for the intent parser to save cost; reserve Sonnet/Pro for execution.
- The `SkillRegistry.reload()` method is called before every execution to pick up new skills without restarting.

## Adding a New Skill

Create a `.md` file in `skills_library/` with this structure:

```markdown
---
name: my-skill
description: "One-line description of what this skill does."
tags:
  - coding
  - review
model_preference: claude
---

# My Skill

System prompt content goes here...
```

Required frontmatter fields: `name`, `description`, `tags`.
Optional: `model_preference` (`claude` | `gemini` | `auto`).
