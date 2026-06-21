"""Generate Chinese tiered notes from uploaded course PDFs."""
from __future__ import annotations

from pathlib import Path

from core.base_agent import BaseAgent
from core.config import Settings
from core.llm_router import LLMRouter
from core.pdf_parser import ParsedPDF, parse_week_inputs
from core.validators import SYNTHESIS_RULES

TIERS: dict[str, str] = {
    "Beginner": "基础层。面向刚接触该主题的学生，讲清楚概念是什么、为什么重要、基本组成和入门例子。",
    "Intermediate": "应用层。面向已经理解基础概念的学生，重点讲清楚步骤、方法、应用场景、典型题型和实践过程。",
    "Advanced": "提升层。面向需要深入理解的学生，补充原理、边界条件、复杂案例、工程权衡和拓展思考。",
}


class IngestionAgent(BaseAgent):
    def __init__(self, settings: Settings, router: LLMRouter):
        super().__init__("ingestion", settings, router, system_prompt_file="ingestion_zh.md")
        extras = self.route.extras
        self.ocr = bool(extras.get("ocr", True))
        self.ocr_langs = str(extras.get("ocr_langs", "chi_sim+eng"))
        self.ocr_min_chars = int(extras.get("ocr_min_chars", 40))
        self.max_tokens = int(extras.get("max_tokens", 12000))

    def ingest_week(self, week_dir: Path, week: int) -> dict[str, Path]:
        """Parse PDFs and synthesize the three tier files."""
        parsed = parse_week_inputs(
            week_dir / "input",
            week_dir / "assets",
            ocr=self.ocr,
            ocr_langs=self.ocr_langs,
            ocr_min_chars=self.ocr_min_chars,
        )
        if not parsed:
            raise FileNotFoundError(f"No PDFs in {week_dir / 'input'}.")

        outputs: dict[str, Path] = {}
        for tier, guidance in TIERS.items():
            system = (
                self.system_prompt
                .replace("{{TIER}}", tier)
                .replace("{{TIER_GUIDANCE}}", guidance)
            )
            sections = [
                self._synthesize_source(system, tier, week, pdf)
                for pdf in parsed
                if pdf.full_text.strip()
            ]
            out_path = week_dir / f"{tier}.md"
            out_path.write_text(self._assemble(tier, week, sections), encoding="utf-8")
            outputs[tier] = out_path
        return outputs

    def _synthesize_source(self, system: str, tier: str, week: int, parsed: ParsedPDF) -> str:
        user = {
            "role": "user",
            "content": (
                f"下面是第 {week} 周课程资料《{parsed.source.name}》提取/OCR 得到的文本。"
                "文本可能包含断行、错别字或少量识别错误，请合理修正。"
                f"请为该资料生成 **{tier}** 层级的中文讲义，覆盖资料中出现的关键主题，"
                "不要遗漏主要知识点。\n\n"
                f"--- 课程资料文本（{parsed.source.name}）---\n"
                f"{parsed.full_text}\n"
                "--- 文本结束 ---"
            ),
        }
        return self.run_validated(
            [user],
            SYNTHESIS_RULES,
            system=system,
            max_tokens=self.max_tokens,
        ).strip()

    @staticmethod
    def _assemble(tier: str, week: int, sections: list[str]) -> str:
        if not sections:
            return (
                f"# {tier} - 第 {week:02d} 周\n\n"
                "_未能从 PDF 中提取到可读文本。请尝试上传文字版 PDF，或安装中文 OCR 后重新生成。_\n"
            )
        return "\n\n---\n\n".join(sections) + "\n"
