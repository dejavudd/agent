"""Phase 2 — Retention (Assessment Engine).

Generates a tiered quiz from the week's Phase 1 tier files, interleaving prior-week
questions to force long-term retention. The model returns a structured JSON question
bank *with answer keys*; we persist that as `Quiz.json` (what the interactive,
auto-checked Quiz tab reads) and render an answer-free `Quiz.md` for the Viewer.
Per-tier question counts come from `config.yaml` so the quiz can be resized without
touching code.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.base_agent import BaseAgent
from core.config import Settings
from core.llm_router import LLMRouter
from core.validators import (
    QUIZ_RULES,
    parse_quiz_json,
    valid_quiz_json,
)

TIER_FILES = ("Beginner.md", "Intermediate.md", "Advanced.md")

# Fallback counts if an agent's config.yaml entry omits them.
DEFAULT_COUNTS = {"beginner": 20, "intermediate": 10, "interleaved": 4, "essays": 3}

# Order tiers render in Quiz.md / Answers.md.
_TIER_ORDER = ("Beginner", "Intermediate", "Interleaved", "Advanced")
_TIER_HEADINGS = {
    "Beginner": "Beginner (기초)",
    "Intermediate": "Intermediate (중급)",
    "Interleaved": "Interleaved Review (이전 주 복습)",
    "Advanced": "Advanced Essay Prompts (심화 논술)",
}


@dataclass
class QuizResult:
    quiz_path: Path          # answer-free Quiz.md (Viewer / markdown compat)
    spec_path: Path          # Quiz.json (structured, with answer keys)
    answers_path: Path       # blank Answers.md template (grader fallback)
    interleaved: bool


class QuizAgent(BaseAgent):
    def __init__(self, settings: Settings, router: LLMRouter):
        super().__init__("quiz", settings, router, system_prompt_file="quiz_zh.md")

    def build_quiz(self, week_dir: Path, week: int, prior_weeks: list[int]) -> QuizResult:
        """Generate Quiz.json + an answer-free Quiz.md + a blank Answers.md."""
        tier_text = self._read_tiers(week_dir)
        if not tier_text:
            raise FileNotFoundError(
                f"No tier notes in {week_dir}. Run `ingest` for Week {week:02d} first."
            )
        prior_text = self._read_prior(week_dir.parent, prior_weeks)
        interleave = bool(prior_text)
        counts = self._counts(interleave)

        system = self.system_prompt.replace("{{WEEK}}", str(week))
        user = self._build_user_prompt(week, tier_text, prior_text, counts, interleave)

        validators = QUIZ_RULES + [valid_quiz_json(counts, interleave)]
        # A ~37-question bank with answer keys + explanations needs generous headroom.
        raw = self.run_validated(
            [{"role": "user", "content": user}], validators, system=system, max_tokens=16000
        )

        spec = parse_quiz_json(raw)
        if spec is None or not isinstance(spec.get("questions"), list):
            raise ValueError(
                "The quiz model did not return parseable JSON after retries. "
                "Try regenerating; if it persists, lower the requested counts in config.yaml."
            )
        spec.setdefault("week", week)
        questions = spec["questions"]

        spec_path = week_dir / "Quiz.json"
        quiz_path = week_dir / "Quiz.md"
        answers_path = week_dir / "Answers.md"

        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        quiz_path.write_text(self._render_quiz_md(week, questions), encoding="utf-8")
        # Don't clobber answers the student already wrote.
        if not answers_path.exists():
            answers_path.write_text(self._render_answers_template(week, questions), encoding="utf-8")

        return QuizResult(
            quiz_path=quiz_path, spec_path=spec_path,
            answers_path=answers_path, interleaved=interleave,
        )

    # ----------------------------------------------------------------- prompt
    def _counts(self, interleave: bool) -> dict:
        extras = self.route.extras
        counts = {k: int(extras.get(k, DEFAULT_COUNTS[k])) for k in DEFAULT_COUNTS}
        if not interleave:
            counts["interleaved"] = 0
        return counts

    @staticmethod
    def _build_user_prompt(week, tier_text, prior_text, counts, interleave) -> str:
        lines = [
            f"Generate the Week {week} quiz as a single JSON object per your directives.",
            "",
            "Produce approximately these many questions per tier (honor these counts):",
            f"- Beginner: {counts['beginner']} (mostly mcq/cloze, some short definitions)",
            f"- Intermediate: {counts['intermediate']} (short application/logic problems)",
            f"- Advanced: {counts['essays']} essay prompts",
        ]
        if interleave:
            lines.append(
                f"- Interleaved: {counts['interleaved']} questions drawn from the PRIOR weeks below"
            )
        lines += ["", "=== THIS WEEK'S NOTES ===", tier_text]
        if interleave:
            lines += ["", "=== PRIOR WEEKS (source for the Interleaved questions) ===", prior_text]
        else:
            lines += ["", "(No prior weeks — omit Interleaved questions.)"]
        return "\n".join(lines)

    # ----------------------------------------------------------------- render
    @staticmethod
    def _render_quiz_md(week: int, questions: list[dict]) -> str:
        """Human-readable, ANSWER-FREE markdown grouped by tier (for the Viewer)."""
        out = [f"# Week {week} Quiz", ""]
        for tier in _TIER_ORDER:
            group = [q for q in questions if q.get("tier") == tier]
            if not group:
                continue
            out.append(f"## {_TIER_HEADINGS.get(tier, tier)}")
            for n, q in enumerate(group, 1):
                prompt = str(q.get("prompt", "")).strip()
                if q.get("type") == "essay":
                    out.append(f"{n}. > {prompt}")
                else:
                    out.append(f"{n}. ({q.get('type')}) {prompt}")
                    for opt in q.get("options") or []:
                        out.append(f"   - {opt}")
            out.append("")
        return "\n".join(out).strip() + "\n"

    @staticmethod
    def _render_answers_template(week: int, questions: list[dict]) -> str:
        """Blank template mirroring question ids (grader fallback; essays excluded)."""
        out = [f"# Week {week} — My Answers", ""]
        for tier in _TIER_ORDER:
            group = [q for q in questions if q.get("tier") == tier and q.get("type") != "essay"]
            if not group:
                continue
            out.append(f"## {_TIER_HEADINGS.get(tier, tier)}")
            for q in group:
                out.append(f"- {q.get('id', '?')}: ")
            out.append("")
        return "\n".join(out).strip() + "\n"

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _read_tiers(week_dir: Path) -> str:
        parts = []
        for name in TIER_FILES:
            p = week_dir / name
            if p.exists():
                parts.append(f"--- {name} ---\n{p.read_text(encoding='utf-8')}")
        return "\n\n".join(parts).strip()

    @staticmethod
    def _read_prior(curriculum: Path, prior_weeks: list[int]) -> str:
        """Condensed prior-week material (Beginner tier is enough for interleaving)."""
        parts = []
        for w in prior_weeks:
            wdir = curriculum / f"Week_{w:02d}"
            for name in ("Beginner.md", "Intermediate.md"):
                p = wdir / name
                if p.exists():
                    parts.append(f"--- Week {w:02d} / {name} ---\n{p.read_text(encoding='utf-8')}")
        return "\n\n".join(parts).strip()


_TIER_HEADINGS = {
    "Beginner": "基础题",
    "Intermediate": "应用题",
    "Interleaved": "复习题",
    "Advanced": "综合题",
}


def _build_user_prompt_zh(week, tier_text, prior_text, counts, interleave) -> str:
    lines = [
        f"请按照系统要求生成第 {week} 周测评题库，只返回一个 JSON 对象。",
        "",
        "请尽量按照以下数量生成各层级题目：",
        f"- Beginner: {counts['beginner']} 题，主要为单选、填空和基础简答",
        f"- Intermediate: {counts['intermediate']} 题，主要为应用、步骤和逻辑分析",
        f"- Advanced: {counts['essays']} 题，主要为综合分析题",
    ]
    if interleave:
        lines.append(f"- Interleaved: {counts['interleaved']} 题，基于下面的前几周资料")
    lines += ["", "=== 本周讲义 ===", tier_text]
    if interleave:
        lines += ["", "=== 前几周资料（用于生成复习题）===", prior_text]
    else:
        lines += ["", "没有前几周资料，请不要生成 Interleaved 复习题。"]
    return "\n".join(lines)


def _render_quiz_md_zh(week: int, questions: list[dict]) -> str:
    out = [f"# 第 {week} 周智能测评", ""]
    for tier in _TIER_ORDER:
        group = [q for q in questions if q.get("tier") == tier]
        if not group:
            continue
        out.append(f"## {_TIER_HEADINGS.get(tier, tier)}")
        for n, q in enumerate(group, 1):
            prompt = str(q.get("prompt", "")).strip()
            if q.get("type") == "essay":
                out.append(f"{n}. > {prompt}")
            else:
                out.append(f"{n}. ({q.get('type')}) {prompt}")
                for opt in q.get("options") or []:
                    out.append(f"   - {opt}")
        out.append("")
    return "\n".join(out).strip() + "\n"


def _render_answers_template_zh(week: int, questions: list[dict]) -> str:
    out = [f"# 第 {week} 周我的答案", ""]
    for tier in _TIER_ORDER:
        group = [q for q in questions if q.get("tier") == tier and q.get("type") != "essay"]
        if not group:
            continue
        out.append(f"## {_TIER_HEADINGS.get(tier, tier)}")
        for q in group:
            out.append(f"- {q.get('id', '?')}: ")
        out.append("")
    return "\n".join(out).strip() + "\n"


QuizAgent._build_user_prompt = staticmethod(_build_user_prompt_zh)
QuizAgent._render_quiz_md = staticmethod(_render_quiz_md_zh)
QuizAgent._render_answers_template = staticmethod(_render_answers_template_zh)
