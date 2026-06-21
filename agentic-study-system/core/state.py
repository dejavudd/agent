"""Diagnostic.md — the evolving state file for Phase 3 (Review).

This Markdown file is both human-readable study feedback and the shared memory
between Agent A (Socratic Dismantler) and Agent B (Feynman Pupil). Using a file
as the message bus is deliberate: the orchestrator passes a path, not content,
so the main context window never fills with essays and critiques.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

_TEMPLATE = """# Diagnostic — Learning State

> Evolving record of strengths, weaknesses, and conceptual gaps.
> Updated automatically after every week's Review phase. Do not hand-edit the
> Findings Log; curate the summary sections freely.

## Strengths
_None recorded yet._

## Weaknesses
_None recorded yet._

## Conceptual Gaps
_None recorded yet._

## Findings Log
<!-- Append-only. Each entry: date · week · agent · finding. -->
"""


class Diagnostic:
    """Read/append helper around a single Diagnostic.md file."""

    def __init__(self, path: Path):
        self.path = path

    @classmethod
    def open(cls, path: Path) -> "Diagnostic":
        """Return a Diagnostic, creating the file from template if absent."""
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(_TEMPLATE, encoding="utf-8")
        return cls(path)

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def append_finding(self, week: int, agent: str, finding: str) -> None:
        """Add one entry to the append-only Findings Log."""
        finding = finding.strip().replace("\n", " ")
        entry = f"- **{date.today().isoformat()}** · Week {week:02d} · _{agent}_ — {finding}\n"
        text = self.read()
        marker = "## Findings Log"
        if marker in text:
            head, _, tail = text.partition(marker)
            # tail starts with the heading remainder + the HTML comment line.
            text = head + marker + tail.rstrip() + "\n" + entry
        else:  # tolerate a hand-trimmed file
            text = text.rstrip() + f"\n\n{marker}\n" + entry
        self.path.write_text(text, encoding="utf-8")

    def append_findings(self, week: int, agent: str, findings: list[str]) -> int:
        for f in findings:
            if f.strip():
                self.append_finding(week, agent, f)
        return len([f for f in findings if f.strip()])

    def append_section(self, title: str, body: str) -> None:
        """Append a free-form Markdown section (e.g. a Feynman session summary)."""
        block = f"\n## {title}\n{body.strip()}\n"
        self.path.write_text(self.read().rstrip() + "\n" + block, encoding="utf-8")
