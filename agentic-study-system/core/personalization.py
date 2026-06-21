"""Student profile storage and rendering helpers.

The competition workflow needs a stable "student image" that can be updated as
the learner studies. Keep the canonical data in JSON for agents and render a
human-readable Markdown copy for the UI and submission evidence.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


PROFILE_JSON = "Profile.json"
PROFILE_MD = "Profile.md"
LEARNING_PATH_MD = "LearningPath.md"

DEFAULT_PROFILE: dict[str, Any] = {
    "basic": {
        "major": "",
        "grade": "",
        "target_course": "",
        "learning_goal": "",
        "time_budget": "",
    },
    "dimensions": {
        "knowledge_base": "",
        "cognitive_style": "",
        "weak_points": "",
        "interests": "",
        "resource_preferences": "",
        "assessment_preference": "",
    },
    "state": {
        "progress_summary": "",
        "last_updated": "",
    },
    "raw_notes": "",
}


def profile_paths(subject_dir: Path) -> tuple[Path, Path]:
    return subject_dir / PROFILE_JSON, subject_dir / PROFILE_MD


def load_profile(subject_dir: Path) -> dict[str, Any]:
    json_path, md_path = profile_paths(subject_dir)
    if not json_path.exists():
        profile = deepcopy(DEFAULT_PROFILE)
        save_profile(subject_dir, profile)
        return profile
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    profile = merge_profile(DEFAULT_PROFILE, data)
    if not md_path.exists():
        md_path.write_text(render_profile(profile), encoding="utf-8")
    return profile


def save_profile(subject_dir: Path, profile: dict[str, Any]) -> dict[str, Any]:
    subject_dir.mkdir(parents=True, exist_ok=True)
    normalized = merge_profile(DEFAULT_PROFILE, profile)
    normalized["state"]["last_updated"] = date.today().isoformat()
    json_path, md_path = profile_paths(subject_dir)
    json_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(render_profile(normalized), encoding="utf-8")
    return normalized


def append_profile_signal(subject_dir: Path, signal: str, *, category: str = "auto") -> dict[str, Any]:
    """Fast deterministic profile update used after learning events.

    The LLM profile agent can later refine these notes. This keeps "automatic"
    profile updates available even when the API is temporarily unavailable.
    """
    profile = load_profile(subject_dir)
    signal = signal.strip()
    if not signal:
        return profile
    existing = str(profile.get("raw_notes", "")).strip()
    line = f"- [{date.today().isoformat()}][{category}] {signal}"
    profile["raw_notes"] = (existing + "\n" + line).strip() if existing else line
    progress = str(profile["state"].get("progress_summary", "")).strip()
    if category in {"grade", "effect", "rag", "chat"}:
        profile["state"]["progress_summary"] = (
            f"{progress}\n{line}".strip() if progress else line
        )
    return save_profile(subject_dir, profile)


def merge_profile(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for section, values in (incoming or {}).items():
        if isinstance(values, dict) and isinstance(out.get(section), dict):
            for key, value in values.items():
                if key in out[section]:
                    out[section][key] = "" if value is None else str(value)
        elif section in out:
            out[section] = values
    return out


def render_profile(profile: dict[str, Any]) -> str:
    basic = profile.get("basic", {})
    dims = profile.get("dimensions", {})
    state = profile.get("state", {})
    rows = [
        ("专业背景", basic.get("major", "")),
        ("年级/层次", basic.get("grade", "")),
        ("目标课程", basic.get("target_course", "")),
        ("学习目标", basic.get("learning_goal", "")),
        ("时间投入", basic.get("time_budget", "")),
        ("知识基础", dims.get("knowledge_base", "")),
        ("认知风格", dims.get("cognitive_style", "")),
        ("知识短板", dims.get("weak_points", "")),
        ("兴趣方向", dims.get("interests", "")),
        ("资源偏好", dims.get("resource_preferences", "")),
        ("测评偏好", dims.get("assessment_preference", "")),
        ("学习进度", state.get("progress_summary", "")),
    ]
    lines = [
        "# 学习画像",
        "",
        f"最后更新：{state.get('last_updated') or date.today().isoformat()}",
        "",
        "| 维度 | 当前信号 |",
        "| --- | --- |",
    ]
    for key, value in rows:
        lines.append(f"| {key} | {escape_table(value) or '_暂未记录_'} |")
    raw = str(profile.get("raw_notes", "")).strip()
    if raw:
        lines += ["", "## 访谈记录 / 行为观察", raw]
    return "\n".join(lines).rstrip() + "\n"


def escape_table(value: Any) -> str:
    return str(value or "").replace("\n", "<br>").replace("|", "\\|").strip()
