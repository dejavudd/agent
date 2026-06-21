"""Generate concrete learning artifacts from the resource package.

These artifacts are intentionally dependency-free: Markdown, HTML, and Mermaid
source files are enough for a runnable competition prototype. They can later be
exported to PPTX/video by external tools.
"""
from __future__ import annotations

import html
import re
from pathlib import Path


ARTIFACT_DIR = "generated_assets"


def generate_artifacts(week_dir: Path, resource_markdown: str) -> list[Path]:
    out_dir = week_dir / ARTIFACT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        _write_ppt_outline(out_dir, resource_markdown),
        _write_video_script(out_dir, resource_markdown),
        _write_interactive_case(out_dir, resource_markdown),
        _write_mindmap_source(out_dir, resource_markdown),
    ]
    return outputs


def _write_ppt_outline(out_dir: Path, markdown: str) -> Path:
    sections = _headings(markdown)[:8] or ["Learning Goal", "Key Concepts", "Practice", "Review"]
    lines = ["# PPT Outline", ""]
    for idx, title in enumerate(sections, 1):
        lines += [
            f"## Slide {idx}: {title}",
            "- Core message:",
            "- Visual suggestion:",
            "- Speaker note:",
            "",
        ]
    path = out_dir / "PPT_Outline.md"
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def _write_video_script(out_dir: Path, markdown: str) -> Path:
    summary = _plain(markdown)[:1800]
    lines = [
        "# Micro Video Script",
        "",
        "## Scene 1 - Hook",
        "Introduce the learner's pain point and the concrete concept to solve.",
        "",
        "## Scene 2 - Explanation",
        summary,
        "",
        "## Scene 3 - Worked Example",
        "Show one step-by-step example and pause before the final answer.",
        "",
        "## Scene 4 - Checkpoint",
        "Ask the learner to predict the next step, then reveal the reasoning.",
    ]
    path = out_dir / "Video_Script.md"
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def _write_interactive_case(out_dir: Path, markdown: str) -> Path:
    text = html.escape(_plain(markdown)[:2400])
    path = out_dir / "Interactive_Case.html"
    path.write_text(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Interactive Learning Case</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 0; background: #10141a; color: #e9edf3; }}
    main {{ max-width: 900px; margin: 0 auto; padding: 28px; }}
    textarea {{ width: 100%; min-height: 110px; border-radius: 8px; padding: 12px; }}
    button {{ margin-top: 10px; padding: 8px 12px; border-radius: 7px; }}
    .panel {{ border: 1px solid #303946; background: #171d26; border-radius: 8px; padding: 16px; margin: 12px 0; }}
    .hidden {{ display: none; }}
  </style>
</head>
<body>
<main>
  <h1>Interactive Learning Case</h1>
  <section class="panel"><p>{text}</p></section>
  <section class="panel">
    <h2>Try It</h2>
    <p>Explain the key idea in your own words, then compare with the hint.</p>
    <textarea id="answer" placeholder="Your explanation"></textarea>
    <br><button onclick="document.getElementById('hint').classList.toggle('hidden')">Toggle Hint</button>
    <div id="hint" class="panel hidden">Check whether your explanation includes the concept, one example, and one limitation.</div>
  </section>
</main>
</body>
</html>
""", encoding="utf-8")
    return path


def _write_mindmap_source(out_dir: Path, markdown: str) -> Path:
    headings = _headings(markdown)[:10] or ["Concept", "Example", "Practice"]
    lines = ["```mermaid", "mindmap", "  root((Personalized Resources))"]
    for heading in headings:
        safe = re.sub(r"[:()\[\]{}]", " ", heading).strip()[:60]
        lines.append(f"    {safe or 'Topic'}")
    lines.append("```")
    path = out_dir / "Mindmap.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _headings(markdown: str) -> list[str]:
    return [
        line.lstrip("#").strip()
        for line in markdown.splitlines()
        if line.startswith("#") and line.lstrip("#").strip()
    ]


def _plain(markdown: str) -> str:
    text = re.sub(r"```.*?```", "", markdown, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
    text = re.sub(r"[#*_>`|~-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

