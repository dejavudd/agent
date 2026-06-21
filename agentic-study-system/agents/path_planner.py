"""Personalized learning path planner."""
from __future__ import annotations

from pathlib import Path

from core.base_agent import BaseAgent
from core.config import Settings
from core.llm_router import LLMRouter
from core.safety import check_text


LEARNING_PATH_OUTPUT = "LearningPath.md"


class PathPlannerAgent(BaseAgent):
    def __init__(self, settings: Settings, router: LLMRouter):
        super().__init__("path_planner", settings, router, "path_planner_zh.md")

    def plan(
        self,
        *,
        subject_dir: Path,
        subject_name: str,
        profile_markdown: str,
        diagnostic_text: str,
        weeks_summary: str,
    ) -> Path:
        user = {
            "role": "user",
            "content": (
                f"请为该课程创建或刷新个性化学习路径，全部使用简体中文。\n\n"
                f"课程：{subject_name}\n\n"
                f"学生画像：\n{profile_markdown or '无'}\n\n"
                f"诊断记录：\n{diagnostic_text or '无'}\n\n"
                f"学习单元状态：\n{weeks_summary or '无'}"
            ),
        }
        markdown = self.run([user], max_tokens=9000)
        context = "\n\n".join([profile_markdown, diagnostic_text, weeks_summary])
        check_text(markdown, context=context)
        out = subject_dir / LEARNING_PATH_OUTPUT
        out.write_text(markdown.strip() + "\n", encoding="utf-8")
        return out
