"""
Scrape skills.sh for high-rated community skills and save them to skills_library/.

This script is designed to run in the GitHub Actions workflow. It fetches the
skills.sh page, parses skill entries, and writes new SKILL.md files for any
high-rated skills not already present in the library.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
import yaml


SKILLS_SH_URL = "https://skills.sh"
SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", "skills_library"))
MIN_RATING_THRESHOLD = 4.0  # Only import skills rated 4.0+


def fetch_page() -> str:
    """Fetch the skills.sh homepage."""
    resp = httpx.get(SKILLS_SH_URL, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def parse_skills(html: str) -> list[dict]:
    """
    Parse skill entries from the skills.sh HTML.

    This parser looks for common patterns in the skills.sh page structure.
    It may need adjustment if the site layout changes.
    """
    soup = BeautifulSoup(html, "html.parser")
    skills = []

    # Look for skill cards/entries — adapt selectors to actual site structure
    for card in soup.select("[data-skill], .skill-card, .skill-item, article"):
        name = ""
        description = ""
        tags: list[str] = []
        rating = 0.0

        # Try to extract name
        name_el = card.select_one("h2, h3, .skill-name, [data-skill-name]")
        if name_el:
            name = name_el.get_text(strip=True)

        # Try to extract description
        desc_el = card.select_one("p, .skill-description, [data-skill-desc]")
        if desc_el:
            description = desc_el.get_text(strip=True)

        # Try to extract tags
        for tag_el in card.select(".tag, .skill-tag, [data-tag]"):
            tags.append(tag_el.get_text(strip=True).lower())

        # Try to extract rating
        rating_el = card.select_one(".rating, [data-rating], .stars")
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", rating_text)
            if match:
                rating = float(match.group(1))

        # Also check data attributes
        if not name and card.get("data-skill"):
            name = card["data-skill"]
        if card.get("data-rating"):
            try:
                rating = float(card["data-rating"])
            except ValueError:
                pass

        if name and description:
            skills.append({
                "name": name,
                "description": description,
                "tags": tags or ["general"],
                "rating": rating,
            })

    return skills


def slugify(name: str) -> str:
    """Convert a skill name to a filename-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")


def skill_exists(name: str) -> bool:
    """Check if a skill with this name already exists in the library."""
    slug = slugify(name)
    for path in SKILLS_DIR.glob("*.md"):
        if path.stem == slug:
            return True
        # Also check the frontmatter name
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if match:
            try:
                meta = yaml.safe_load(match.group(1))
                if isinstance(meta, dict) and meta.get("name") == name:
                    return True
            except yaml.YAMLError:
                pass
    return False


def write_skill(skill: dict) -> Path:
    """Write a skill as a SKILL.md file."""
    slug = slugify(skill["name"])
    path = SKILLS_DIR / f"{slug}.md"

    frontmatter = yaml.dump(
        {
            "name": skill["name"],
            "description": skill["description"],
            "tags": skill["tags"],
            "model_preference": "auto",
            "source": "skills.sh",
            "rating": skill["rating"],
        },
        default_flow_style=False,
        sort_keys=False,
    ).strip()

    content = f"""---
{frontmatter}
---

# {skill['name']}

{skill['description']}

_This skill was automatically imported from [skills.sh]({SKILLS_SH_URL})._
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching skills from {SKILLS_SH_URL}...")
    try:
        html = fetch_page()
    except httpx.HTTPError as e:
        print(f"Failed to fetch skills.sh: {e}")
        return

    skills = parse_skills(html)
    print(f"Found {len(skills)} skills on skills.sh")

    new_count = 0
    for skill in skills:
        if skill["rating"] < MIN_RATING_THRESHOLD:
            continue
        if skill_exists(skill["name"]):
            print(f"  Skipping '{skill['name']}' — already exists")
            continue

        path = write_skill(skill)
        print(f"  Added '{skill['name']}' → {path}")
        new_count += 1

    print(f"\nDone. Added {new_count} new skill(s).")


if __name__ == "__main__":
    main()
