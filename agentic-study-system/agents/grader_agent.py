"""Phase 2 — Feedback / "check grading" engine.

Reviews the student's quiz answers and reports current understanding, specific
lacks, and improvement paths. Obeys Metacognitive Scaffolding: it traces where
reasoning broke down rather than stamping Correct/Incorrect (enforced by
core.validators). Findings are appended to Diagnostic.md so state evolves weekly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from core.base_agent import BaseAgent
from core.config import Settings
from core.llm_router import LLMRouter
from core.state import Diagnostic
from core.validators import GRADER_RULES

# Same finding format as the Socratic Dismantler: "- [gap] ..." / "- [weakness] ..."
_FINDING = re.compile(r"^\s*[-*]\s*\[(gap|weakness)\]\s*(.+?)\s*$", re.IGNORECASE)


@dataclass
class GradeResult:
    feedback_markdown: str
    feedback_path: Path
    findings: list[str]


class GraderAgent(BaseAgent):
    def __init__(self, settings: Settings, router: LLMRouter):
        super().__init__("grader", settings, router, system_prompt_file="grader_zh.md")

    def grade(
        self,
        quiz_path: Path,
        answers_path: Path,
        week: int,
        diagnostic: Diagnostic | None = None,
    ) -> GradeResult:
        if not quiz_path.exists():
            raise FileNotFoundError(
                f"Quiz not found: {quiz_path}. Run `quiz` for Week {week:02d} first."
            )
        if not answers_path.exists():
            raise FileNotFoundError(
                f"Answers not found: {answers_path}. Fill in Answers.md before grading."
            )
        quiz = quiz_path.read_text(encoding="utf-8").strip()
        answers = answers_path.read_text(encoding="utf-8").strip()
        if not answers or _looks_empty(answers):
            raise ValueError(
                f"No answers written yet in {answers_path.name}. Fill it in, then grade."
            )

        system = self.system_prompt.replace("{{WEEK}}", str(week))
        user = (
            f"下面是第 {week} 周测评题目和学生答案。请按照系统要求给出中文学习诊断。"
            f"\n\n=== 测评题目 ===\n{quiz}\n\n=== 学生答案 ===\n{answers}"
        )
        feedback = self.run_validated(
            [{"role": "user", "content": user}], GRADER_RULES, system=system
        )

        feedback_path = quiz_path.parent / "Feedback.md"
        feedback_path.write_text(feedback, encoding="utf-8")

        findings = self._extract_findings(feedback)
        if diagnostic is not None:
            diagnostic.append_findings(week, "Diagnostic Coach", findings)

        return GradeResult(
            feedback_markdown=feedback, feedback_path=feedback_path, findings=findings
        )

    @staticmethod
    def _extract_findings(feedback: str) -> list[str]:
        out: list[str] = []
        for line in feedback.splitlines():
            m = _FINDING.match(line)
            if m:
                out.append(f"[{m.group(1).lower()}] {m.group(2)}")
        return out


def _looks_empty(answers: str) -> bool:
    """True if Answers.md still only has headings / template scaffolding, no content."""
    content = [
        ln for ln in answers.splitlines()
        if ln.strip()
        and not ln.lstrip().startswith("#")
        and not ln.strip().startswith("_")
        and not re.match(r"^\s*\d+\.\s*$", ln)        # bare "1." with no answer
    ]
    return not content
