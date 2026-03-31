# Skill-Aware Router

A **Skills.sh Orchestration Layer** built on [FastMCP 3.0](https://gofastmcp.com). It treats every **Model + Skill** combination as a single unit of execution, automatically routing user prompts to the best-fit pair.

## How It Works

```
User Prompt
    │
    ▼
┌──────────────────────┐
│  1. ROUTER           │  Gemini 1.5 Flash analyzes the prompt
│     (Fast + Cheap)   │  against all skill descriptions
└──────────┬───────────┘
           │ best-match skill
           ▼
┌──────────────────────┐
│  2. SELECTOR         │  Skill tags determine the execution model:
│     (Tag-Based)      │  coding/logic → Claude Sonnet
│                      │  research/data → Gemini 1.5 Pro
└──────────┬───────────┘
           │ model + skill body
           ▼
┌──────────────────────┐
│  3. EXECUTOR         │  Skill content injected as system prompt,
│     (Model Call)     │  chosen model generates the response
└──────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- API keys for [Anthropic](https://console.anthropic.com/) and [Google AI](https://aistudio.google.com/apikey)

### Setup

```bash
# Clone the repo
git clone https://github.com/<your-username>/skill-aware-router.git
cd skill-aware-router

# Install dependencies
uv sync

# Configure API keys
cp .env.example .env
# Edit .env with your keys

# Run the MCP server
uv run fastmcp run main.py:mcp
```

### Use with Cursor

The repo includes `.cursor/mcp.json` — Cursor will auto-detect the server. Make sure your environment variables are set.

### Use with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "skill-router": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "main.py:mcp"],
      "cwd": "/path/to/skill-aware-router"
    }
  }
}
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `execute_smart_task(prompt)` | Route a prompt to the best skill+model pair and return the result |
| `list_skills()` | List all registered skills with their metadata |
| `reload_skills()` | Force-reload skills from the `skills_library/` directory |

## Adding Your Own Skills

Drop a Markdown file into `skills_library/` with YAML frontmatter:

```markdown
---
name: my-custom-skill
description: "What this skill does in one line."
tags:
  - coding
  - review
model_preference: claude   # claude | gemini | auto
---

# My Custom Skill

Your system prompt goes here. This content is injected as the system
prompt when this skill is selected for execution.
```

**Tag routing rules:**
- `coding`, `logic`, `code`, `review`, `debug`, `refactor` → routes to **Claude Sonnet**
- `research`, `data`, `analysis`, `search`, `report` → routes to **Gemini 1.5 Pro**

No code changes required — the registry auto-discovers new skills on every call.

## Architecture

- **Framework**: FastMCP 3.0 (MCP-compliant server)
- **Router Model**: Gemini 1.5 Flash (fast, cheap intent classification)
- **Execution Models**: Claude Sonnet (coding tasks), Gemini 1.5 Pro (research tasks)
- **Skill Storage**: Filesystem-based (`skills_library/*.md`) with YAML frontmatter
- **Transport**: stdio (default) or HTTP

## GitHub Action: Skills.sh Scraper

The included GitHub Action (`.github/workflows/scrape-skills.yml`) runs weekly to check [skills.sh](https://skills.sh) for new high-rated community skills. When new skills are found, it automatically opens a Pull Request to add them to `skills_library/`.

## License

MIT
