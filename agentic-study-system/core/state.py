"""Diagnostic.md — the evolving state file for Phase 3 (Review).

This Markdown file is both human-readable study feedback and the shared memory
between Agent A (Socratic Dismantler) and Agent B (Feynman Pupil). Using a file
as the message bus is deliberate: the orchestrator passes a path, not content,
so the main context window never fills with essays and critiques.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

_FINDINGS_MARKER = "## 诊断发现日志"
_LEGACY_FINDINGS_MARKER = "## Findings Log"

_TEMPLATE = """# 学习诊断 — 学习状态

> 这里记录学习优势、薄弱环节和概念缺口。系统会在测评反馈后持续追加诊断发现；上方摘要部分可按需要人工整理。

## 优势表现
_暂无记录。_

## 薄弱环节
_暂无记录。_

## 概念缺口
_暂无记录。_

## 诊断发现日志
<!-- 追加记录：日期 · 章节 · 智能体 · 诊断发现。 -->
"""


def _localize_legacy_template(text: str) -> str:
    """Convert the previous English default headings while preserving entries."""
    replacements = {
        "# Diagnostic — Learning State": "# 学习诊断 — 学习状态",
        "> Evolving record of strengths, weaknesses, and conceptual gaps.\n"
        "> Updated automatically after every week's Review phase. Do not hand-edit the\n"
        "> Findings Log; curate the summary sections freely.": (
            "> 这里记录学习优势、薄弱环节和概念缺口。系统会在测评反馈后持续追加诊断发现；"
            "上方摘要部分可按需要人工整理。"
        ),
        "## Strengths": "## 优势表现",
        "## Weaknesses": "## 薄弱环节",
        "## Conceptual Gaps": "## 概念缺口",
        "_None recorded yet._": "_暂无记录。_",
        _LEGACY_FINDINGS_MARKER: _FINDINGS_MARKER,
        "<!-- Append-only. Each entry: date · week · agent · finding. -->": (
            "<!-- 追加记录：日期 · 章节 · 智能体 · 诊断发现。 -->"
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


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
        text = self.path.read_text(encoding="utf-8")
        localized = _localize_legacy_template(text)
        if localized != text:
            self.path.write_text(localized, encoding="utf-8")
        return localized

    def append_finding(self, week: int, agent: str, finding: str) -> None:
        """Add one entry to the append-only Findings Log."""
        finding = finding.strip().replace("\n", " ")
        entry = f"- **{date.today().isoformat()}** · 第 {week:02d} 章 · _{agent}_ — {finding}\n"
        text = self.read()
        marker = _FINDINGS_MARKER if _FINDINGS_MARKER in text else _LEGACY_FINDINGS_MARKER
        if marker in text:
            head, _, tail = text.partition(marker)
            # tail starts with the heading remainder + the HTML comment line.
            text = head + _FINDINGS_MARKER + tail.rstrip() + "\n" + entry
        else:  # tolerate a hand-trimmed file
            text = text.rstrip() + f"\n\n{_FINDINGS_MARKER}\n" + entry
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
