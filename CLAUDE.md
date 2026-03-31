# Skill-Aware Router — Agent Instructions

## Build/Run Commands

```bash
# Install dependencies
uv sync

# Run the server
uv run main.py

# Run via FastMCP CLI (stdio transport — for Cursor / Claude Desktop)
uv run fastmcp run main.py:mcp

# Run on HTTP (for remote clients)
uv run fastmcp run main.py:mcp --transport http --port 8000
```

## Test

```bash
uv run pytest tests/ -v
```

## Environment

Two API keys are **required** as environment variables:

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude 3.5 Sonnet — executes coding/logic tasks |
| `GOOGLE_API_KEY` | Gemini 1.5 Flash (intent router) + Gemini 1.5 Pro (research executor) |

Copy `.env.example` → `.env` and fill in your keys. Never commit `.env`.

## Project Strategy

This project implements a **two-tier model routing architecture**:

1. **Gemini 1.5 Flash as the Manager/Router** — Every incoming prompt is first analyzed by Gemini Flash. It is fast and cheap, making it ideal for intent classification. It matches the user's prompt against the `description` fields of all registered skills and selects the best one.

2. **Claude 3.5 Sonnet for logic-heavy execution** — When a skill is tagged with `coding`, `logic`, `code`, `review`, `debug`, or `refactor`, the task is routed to Claude Sonnet. Sonnet excels at structured reasoning, code generation, and precise analysis.

3. **Gemini 1.5 Pro for research execution** — When a skill is tagged with `research`, `data`, `analysis`, `search`, or `report`, the task is routed to Gemini Pro. Pro handles broad synthesis and multi-step research well.

The selected skill's Markdown body is injected as the **system prompt** to the chosen model, giving it domain-specific instructions without any code changes.

## Coding Patterns

- **Always use `@mcp.tool()` decorators** for any new routing logic or server capabilities. Every user-facing function must be an MCP tool.
- **Follow the Skills.sh YAML metadata standard** for all files in `skills_library/`. Every skill file must include:
  ```yaml
  ---
  name: skill-name           # Required — unique identifier
  description: "..."         # Required — used by the router for matching
  tags:                      # Required — determines model selection
    - coding
  model_preference: claude   # Optional — claude | gemini | auto
  ---
  ```
- Skills are **plain Markdown** — no Python code. The body after the frontmatter is the system prompt.
- `SkillRegistry.reload()` is called before every execution to hot-reload new skills without restart.
- Use Gemini Flash for the intent parser to save cost; reserve Sonnet/Pro for execution only.

## Architecture

```
User Prompt → Gemini Flash (router) → Tag-based model selector → Execute with skill as system prompt
```

- **FastMCP 3.0** exposes three tools: `list_skills`, `execute_smart_task`, `reload_skills`.
- **SkillRegistry** reads `skills_library/*.md`, parses YAML frontmatter, builds a capability map.
- **GitHub Action** (weekly) scrapes skills.sh for high-rated community skills and opens a PR.
