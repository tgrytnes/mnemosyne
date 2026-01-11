"""
Tagging utilities for the shadow vault (Story 025).
"""

from __future__ import annotations

from pathlib import Path

from mnemosyne.providers.base import LLMProvider


class Tagger:
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider

    def tag_file(self, shadow_file_path: Path) -> list[str]:
        content = Path(shadow_file_path).read_text(encoding="utf-8")
        sample = content[:1000]
        prompt = (
            "Analyze this Obsidian note and suggest relevant tags from this list:\n"
            "- #needs_review\n- #relevant_lessons_learned\n"
            "- #project_candidate\n- #reference_material\n"
            "- #daily_note\n- #meeting_notes\n\n"
            f"Note content:\n{sample}\n\nReturn ONLY the tags (one per line)."
        )
        try:
            response = self.llm_provider.generate(
                model="",
                prompt=prompt,
                options={"temperature": 0.2},
            )
            text = response.get("response", "") if isinstance(response, dict) else str(response)
            lines = text.split("\n")
            tags = [line.strip() for line in lines if line.strip().startswith("#")]
        except Exception:
            tags = []

        # Fallback heuristic if LLM yields nothing
        if not tags:
            lowered = sample.lower()
            if "project" in lowered or "draft" in lowered or "todo" in lowered:
                tags.append("#project_candidate")
            else:
                tags.append("#needs_review")
        return tags

    def apply_tags_to_file(self, shadow_file_path: Path, tags: list[str]):
        content = Path(shadow_file_path).read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            frontmatter = parts[1] if len(parts) >= 2 else ""
            body = parts[2] if len(parts) >= 3 else ""
        else:
            frontmatter = ""
            body = content

        if "tags:" in frontmatter:
            for tag in tags:
                if tag not in frontmatter:
                    frontmatter += f"  - {tag}\n"
        else:
            tag_lines = "\n".join([f"  - {tag}" for tag in tags])
            frontmatter += f"\ntags:\n{tag_lines}\n"

        new_content = f"---{frontmatter}---{body}"
        Path(shadow_file_path).write_text(new_content, encoding="utf-8")
