"""Generate a local Mermaid knowledge diagram from the week's notes."""
from __future__ import annotations

import re
from pathlib import Path

from core.base_agent import BaseAgent
from core.config import Settings
from core.library import TIER_FILES
from core.llm_router import LLMRouter
from core.validators import no_korean_or_mojibake


class WebExplorer(BaseAgent):
    """Kept for API compatibility; now generates diagrams instead of web images."""

    def __init__(self, settings: Settings, router: LLMRouter):
        super().__init__("web_explorer", settings, router)
        self.max_concepts = int(self.route.extras.get("max_concepts", 8))

    def enrich_week(self, week_dir: Path, week: int, concepts: list[str] | None = None) -> dict:
        notes = self._read_notes(week_dir)
        if not notes:
            raise FileNotFoundError(f"No notes found in {week_dir}. Generate notes first.")

        if concepts is None:
            concepts = self._extract_headings(notes)[: self.max_concepts]
        markdown = self._generate_diagram_markdown(week, notes, concepts)

        ok, _ = no_korean_or_mojibake(markdown)
        if not ok or "```mermaid" not in markdown:
            markdown = self._fallback_diagram(week, concepts)

        out = week_dir / "Diagrams.md"
        out.write_text(markdown.strip() + "\n", encoding="utf-8")
        return {"path": out, "count": 1, "concepts": concepts}

    def concepts_from_notes(self, week_dir: Path, week: int) -> list[str]:
        notes = self._read_notes(week_dir)
        return self._extract_headings(notes)[: self.max_concepts] or [f"第 {week} 周知识点"]

    def _generate_diagram_markdown(self, week: int, notes: str, concepts: list[str]) -> str:
        system = (
            "你是知识图解生成智能体。请根据课程讲义生成中文 Markdown，核心是 Mermaid 知识结构图。"
            "不要联网搜索，不要插入外部图片，不要编造资料中没有的事实。"
            "必须使用简体中文。Mermaid 节点文字必须用双引号包裹。"
        )
        user = {
            "role": "user",
            "content": (
                f"请为第 {week} 周课程内容生成知识图解。\n\n"
                "输出结构必须为：\n"
                "# 知识图解\n\n"
                "## 知识结构图\n"
                "```mermaid\nflowchart TD\n...\n```\n\n"
                "## 图解说明\n"
                "- 用 3 到 6 条说明图中的关键关系。\n\n"
                f"建议覆盖的概念：{', '.join(concepts) or '请从讲义中提取'}\n\n"
                f"=== 讲义内容 ===\n{notes[:9000]}"
            ),
        }
        return self.run([user], system=system, max_tokens=3500)

    @staticmethod
    def _read_notes(week_dir: Path) -> str:
        parts: list[str] = []
        for name in TIER_FILES:
            path = week_dir / name
            if path.exists():
                parts.append(f"--- {name} ---\n{path.read_text(encoding='utf-8')[:4000]}")
        return "\n\n".join(parts).strip()

    @staticmethod
    def _extract_headings(notes: str) -> list[str]:
        seen: list[str] = []
        for line in notes.splitlines():
            if not line.startswith("#"):
                continue
            title = re.sub(r"^#+\s*", "", line).strip()
            title = re.sub(r"^[A-Za-z]+\s*[-:：]?\s*", "", title).strip()
            title = re.sub(r"[`*_#>-]", "", title).strip()
            if title and title not in seen and len(title) <= 40:
                seen.append(title)
        return seen

    @staticmethod
    def _fallback_diagram(week: int, concepts: list[str]) -> str:
        nodes = concepts[:6] or [f"第 {week} 周知识点", "核心概念", "应用练习", "复习检测"]
        lines = ["flowchart TD"]
        lines.append(f'  A["第 {week} 周课程内容"] --> B["核心概念"]')
        for index, concept in enumerate(nodes, 1):
            node = f"N{index}"
            safe = concept.replace('"', "'")
            lines.append(f'  B --> {node}["{safe}"]')
        lines.append('  B --> P["练习与测评"]')
        return (
            "# 知识图解\n\n"
            "## 知识结构图\n"
            "```mermaid\n"
            + "\n".join(lines)
            + "\n```\n\n"
            "## 图解说明\n"
            "- 本图根据本周已生成讲义标题自动整理。\n"
            "- 如果图中概念较少，请先重新生成讲义，再生成知识图解。\n"
        )
