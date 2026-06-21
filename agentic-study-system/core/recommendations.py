"""Rule-based adaptive resource push.

This is intentionally deterministic and fast. LLM-generated LearningPath.md is
still useful for narrative planning, but the UI needs immediate next actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.telemetry import read_events


@dataclass
class Recommendation:
    title: str
    reason: str
    action: str
    week: int | None = None
    file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "reason": self.reason,
            "action": self.action,
            "week": self.week,
            "file": self.file,
        }


def build_recommendations(subject_dir: Path, weeks: list[Any], profile: dict[str, Any]) -> list[dict]:
    recs: list[Recommendation] = []
    events = read_events(subject_dir, limit=100)
    event_types = [e.get("type") for e in events]

    if not profile.get("basic", {}).get("learning_goal"):
        recs.append(Recommendation(
            "Complete student image",
            "Learning goal is missing, so resource push cannot be personalized deeply.",
            "profile",
        ))

    for w in weeks:
        if w.status == "New" and w.pdfs:
            recs.append(Recommendation(
                f"Ingest Week {w.week:02d}",
                "Source PDFs exist but tiered notes are not generated.",
                "ingest",
                w.week,
            ))
            continue
        if w.tiers and not w.has_quiz:
            recs.append(Recommendation(
                f"Create Week {w.week:02d} quiz",
                "Quiz practice is needed to check key knowledge points.",
                "quiz",
                w.week,
            ))
        if w.tiers and not getattr(w, "has_extension", False):
            recs.append(Recommendation(
                f"Create Week {w.week:02d} extension materials",
                "Extension materials can provide reading directions and practice cases.",
                "extension",
                w.week,
            ))
        if w.has_quiz and not w.has_feedback:
            recs.append(Recommendation(
                f"Submit Week {w.week:02d} answers",
                "Quiz exists but no deeper feedback has been generated.",
                "open_quiz",
                w.week,
                "Quiz.md",
            ))

    if "rag_ask" not in event_types:
        recs.append(Recommendation(
            "Ask one grounded question",
            "No course-knowledge RAG tutoring event has been recorded yet.",
            "rag",
        ))

    return [r.to_dict() for r in recs[:8]]

