"""Generate lightweight extension learning materials."""
from __future__ import annotations

from pathlib import Path

from core.base_agent import BaseAgent
from core.config import Settings
from core.llm_router import LLMRouter
from core.safety import check_text

EXTENSION_OUTPUT = "Extension.md"


class ExtensionAgent(BaseAgent):
    def __init__(self, settings: Settings, router: LLMRouter):
        super().__init__("extension", settings, router, "extension_materials_zh.md")

    def generate(self, week_dir: Path, week: int) -> Path:
        notes = []
        for name in ("Beginner.md", "Intermediate.md", "Advanced.md", "Diagrams.md"):
            path = week_dir / name
            if path.exists():
                notes.append(f"--- {name} ---\n{path.read_text(encoding='utf-8')[:5000]}")
        if not notes:
            raise FileNotFoundError(f"No notes found in {week_dir}. Generate notes first.")

        user = {
            "role": "user",
            "content": (
                f"请为第 {week:02d} 周生成中文拓展学习材料。\n\n"
                + "\n\n".join(notes)
            ),
        }
        markdown = self.run([user], max_tokens=5000)
        check_text(markdown, context="\n\n".join(notes))

        out = week_dir / EXTENSION_OUTPUT
        out.write_text(markdown.strip() + "\n", encoding="utf-8")
        return out
