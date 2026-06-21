"""Student profile agent.

Turns interview notes, course context, diagnostics, and recent performance into
a stable six-dimension learner profile used by downstream planning agents.
"""
from __future__ import annotations

import json
from typing import Any

from core.base_agent import BaseAgent
from core.config import Settings
from core.llm_router import LLMRouter
from core.personalization import DEFAULT_PROFILE, merge_profile


class ProfileAgent(BaseAgent):
    def __init__(self, settings: Settings, router: LLMRouter):
        super().__init__("profile_builder", settings, router, "profile_builder_zh.md")

    def build(
        self,
        *,
        current_profile: dict[str, Any],
        interview_notes: str,
        diagnostic_text: str,
        subject_name: str,
        weeks_summary: str,
    ) -> dict[str, Any]:
        user = {
            "role": "user",
            "content": (
                "请更新该课程的学生学习画像，字段内容使用简体中文。\n\n"
                f"课程：{subject_name}\n\n"
                f"CURRENT_PROFILE_JSON:\n{json.dumps(current_profile, ensure_ascii=False)}\n\n"
                f"访谈记录：\n{interview_notes or '无'}\n\n"
                f"诊断记录：\n{diagnostic_text or '无'}\n\n"
                f"学习单元状态：\n{weeks_summary or '无'}"
            ),
        }
        raw = self.run([user], max_tokens=3000)
        parsed = _parse_json(raw)
        if not parsed:
            parsed = _fallback_profile(current_profile, interview_notes)
        return merge_profile(DEFAULT_PROFILE, parsed)


def _parse_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    # Strip fenced code block: ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first line (```json or ```) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _fallback_profile(current: dict[str, Any], notes: str) -> dict[str, Any]:
    profile = merge_profile(DEFAULT_PROFILE, current)
    if notes.strip():
        profile["raw_notes"] = notes.strip()
        if not profile["dimensions"]["resource_preferences"]:
            profile["dimensions"]["resource_preferences"] = (
                "需要根据访谈记录进一步推断。"
            )
    return profile
