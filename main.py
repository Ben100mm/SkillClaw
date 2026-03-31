"""
Skill-Aware Router — A Multi-Agent Skill Orchestrator using FastMCP 3.0.

Watches skills_library/ for SKILL.md files, builds a capability map,
and routes user prompts to the best model+skill pair.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from dataclasses import dataclass, field

import yaml
import httpx
from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SKILLS_DIR = Path(__file__).parent / "skills_library"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

CODING_TAGS = {"coding", "logic", "code", "review", "debug", "refactor"}
RESEARCH_TAGS = {"research", "data", "analysis", "search", "report"}

# ---------------------------------------------------------------------------
# Skill data model
# ---------------------------------------------------------------------------


@dataclass
class Skill:
    name: str
    description: str
    tags: list[str]
    model_preference: str
    body: str
    file_path: Path

    @property
    def tag_set(self) -> set[str]:
        return set(self.tags)


# ---------------------------------------------------------------------------
# Skill Registry — filesystem-backed capability map
# ---------------------------------------------------------------------------


class SkillRegistry:
    """Watches skills_library/ and maintains an in-memory capability map."""

    def __init__(self, skills_dir: Path = SKILLS_DIR) -> None:
        self.skills_dir = skills_dir
        self.skills: dict[str, Skill] = {}
        self._load_all()

    # -- loading -----------------------------------------------------------

    def _load_all(self) -> None:
        """Scan the skills directory and parse every .md file."""
        self.skills.clear()
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            return
        for path in sorted(self.skills_dir.glob("*.md")):
            skill = self._parse_skill(path)
            if skill:
                self.skills[skill.name] = skill

    def reload(self) -> int:
        """Re-scan the directory. Returns the number of skills loaded."""
        self._load_all()
        return len(self.skills)

    @staticmethod
    def _parse_skill(path: Path) -> Skill | None:
        """Parse a SKILL.md file with YAML frontmatter."""
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not match:
            return None
        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None
        if not isinstance(meta, dict) or "name" not in meta:
            return None
        return Skill(
            name=meta["name"],
            description=meta.get("description", ""),
            tags=meta.get("tags", []),
            model_preference=meta.get("model_preference", "auto"),
            body=match.group(2).strip(),
            file_path=path,
        )

    # -- querying ----------------------------------------------------------

    def list_skills(self) -> list[dict]:
        """Return a summary of all registered skills."""
        return [
            {"name": s.name, "description": s.description, "tags": s.tags}
            for s in self.skills.values()
        ]

    def find_by_tag(self, tag: str) -> list[Skill]:
        return [s for s in self.skills.values() if tag in s.tag_set]

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)


# ---------------------------------------------------------------------------
# Model Clients
# ---------------------------------------------------------------------------


async def call_gemini_flash(prompt: str, system: str = "") -> str:
    """Call Gemini 1.5 Flash via the Google GenAI REST API."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    headers = {"Content-Type": "application/json"}
    params = {"key": GOOGLE_API_KEY}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def call_gemini_pro(prompt: str, system: str = "") -> str:
    """Call Gemini 1.5 Pro via the Google GenAI REST API."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}
    headers = {"Content-Type": "application/json"}
    params = {"key": GOOGLE_API_KEY}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def call_claude_sonnet(prompt: str, system: str = "") -> str:
    """Call Claude 3.5 Sonnet via the Anthropic Messages API."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data["content"][0]["text"]


# ---------------------------------------------------------------------------
# Router logic
# ---------------------------------------------------------------------------

ROUTER_SYSTEM = """\
You are a skill-routing assistant. Given a user prompt and a list of available
skills (each with a name, description, and tags), respond with ONLY the skill
name that best matches the user's intent. If no skill matches, respond with
"none". Do not explain your reasoning.
"""


async def route_prompt(prompt: str, skills: list[dict]) -> str:
    """Use Gemini Flash to pick the best skill for a prompt."""
    skill_list = "\n".join(
        f"- {s['name']}: {s['description']} (tags: {', '.join(s['tags'])})"
        for s in skills
    )
    router_prompt = (
        f"Available skills:\n{skill_list}\n\nUser prompt:\n{prompt}\n\n"
        "Which skill name should handle this? Reply with the name only."
    )
    result = await call_gemini_flash(router_prompt, system=ROUTER_SYSTEM)
    return result.strip().lower()


def select_model(skill: Skill) -> str:
    """Decide which model to use based on skill tags."""
    tags = skill.tag_set
    if tags & CODING_TAGS:
        return "claude-sonnet"
    if tags & RESEARCH_TAGS:
        return "gemini-pro"
    # Fall back to model_preference or default
    pref = skill.model_preference.lower()
    if pref in ("claude", "anthropic"):
        return "claude-sonnet"
    if pref in ("gemini", "google"):
        return "gemini-pro"
    return "gemini-pro"


async def execute_with_model(model: str, prompt: str, system: str) -> str:
    """Dispatch to the appropriate model client."""
    if model == "claude-sonnet":
        return await call_claude_sonnet(prompt, system=system)
    return await call_gemini_pro(prompt, system=system)


# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Skill-Aware Router",
    instructions=(
        "A multi-agent skill orchestrator. It matches user prompts to "
        "specialized skills and routes execution to the best-fit model."
    ),
)

registry = SkillRegistry()


@mcp.tool
def list_skills() -> list[dict]:
    """List all available skills in the library with their metadata."""
    registry.reload()
    return registry.list_skills()


@mcp.tool
async def execute_smart_task(prompt: str) -> dict:
    """
    Analyze a prompt, match it to the best skill, route to the optimal model,
    and return the result.

    Steps:
      1. Router  — Gemini Flash picks the best skill from the capability map.
      2. Selector — Tags determine which model executes (Claude for coding,
                     Gemini Pro for research).
      3. Executor — The skill body is injected as a system prompt and the
                     chosen model generates the response.
    """
    registry.reload()
    skills = registry.list_skills()

    if not skills:
        return {"error": "No skills found in skills_library/. Add .md files with YAML frontmatter."}

    # Step 1 — Route
    matched_name = await route_prompt(prompt, skills)
    skill = registry.get(matched_name)

    if skill is None:
        return {
            "routed_to": matched_name,
            "error": f"Router returned '{matched_name}' which is not a registered skill.",
            "available_skills": [s["name"] for s in skills],
        }

    # Step 2 — Select model
    model = select_model(skill)

    # Step 3 — Execute
    result = await execute_with_model(model, prompt, system=skill.body)

    return {
        "skill": skill.name,
        "model": model,
        "tags": skill.tags,
        "response": result,
    }


@mcp.tool
def reload_skills() -> dict:
    """Force-reload all skills from the skills_library/ directory."""
    count = registry.reload()
    return {"reloaded": count, "skills": registry.list_skills()}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
