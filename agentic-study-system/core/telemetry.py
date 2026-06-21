"""Lightweight behavior telemetry for adaptive learning.

Events are stored as JSONL under each subject. The goal is not analytics at
scale; it is enough structured evidence for profile refresh, path adjustment,
and effect evaluation.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENTS_JSONL = "BehaviorLog.jsonl"


def log_event(subject_dir: Path, event_type: str, payload: dict[str, Any] | None = None) -> dict:
    subject_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "payload": payload or {},
    }
    with (subject_dir / EVENTS_JSONL).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_events(subject_dir: Path, limit: int = 200) -> list[dict]:
    path = subject_dir / EVENTS_JSONL
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events[-limit:]


def behavior_summary(subject_dir: Path, limit: int = 200) -> str:
    events = read_events(subject_dir, limit=limit)
    if not events:
        return "No behavior events recorded yet."
    counts = Counter(e.get("type", "unknown") for e in events)
    lines = ["Behavior event counts:"]
    lines += [f"- {name}: {count}" for name, count in sorted(counts.items())]
    recent = events[-12:]
    lines += ["", "Recent events:"]
    for event in recent:
        payload = event.get("payload") or {}
        label = payload.get("label") or payload.get("file") or payload.get("question") or ""
        week = payload.get("week")
        where = f" Week {int(week):02d}" if isinstance(week, int) else ""
        lines.append(f"- {event.get('ts', '')} | {event.get('type')}{where} | {label}")
    return "\n".join(lines)

