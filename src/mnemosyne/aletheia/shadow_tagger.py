"""
Tagging utilities for the shadow vault (Story 025).
"""

from __future__ import annotations

from pathlib import Path


class Tagger:
    def __init__(self, ollama_client):
        self.ollama = ollama_client

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
        response = self.ollama.generate(
            model="qwen3:0.6b", prompt=prompt, options={"temperature": 0.2}
        )
        lines = response.get("response", "").split("\n")
        return [line.strip() for line in lines if line.strip().startswith("#")]

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
