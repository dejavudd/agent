#!/usr/bin/env python3
"""Agentic Study System — CLI orchestrator.

Thin coordinator: it wires config -> router -> agents and passes *file paths*
between phases so its own context stays small.

Week commands accept --subject SLUG|NAME (default: the first subject).

Usage:
    python main.py serve   [--port 8000]                       # Web launcher (browser UI)
    python main.py ingest  --week 1 [--subject S]              # Phase 1: synthesize tiered notes
    python main.py explore --week 1 [--subject S]              # Phase 1: fetch reference diagrams
    python main.py extension --week 1 [--subject S]            # Phase 1: extension materials
    python main.py quiz    --week 1 [--subject S]              # Phase 2: build quiz + answers
    python main.py grade   --week 1 [--subject S]              # Phase 2: grade your answers
"""
from __future__ import annotations

import argparse
import sys

from core.config import load_settings
from core.library import Library, SubjectStore, ensure_migrated
from core.llm_router import LLMError, make_router
from core.state import Diagnostic


def _library(settings, subject: str | None) -> Library:
    """Resolve a subject (by slug or name) to a scoped Library; default = first."""
    ensure_migrated(settings.root)
    subs = SubjectStore(settings.root).list_subjects()
    if not subs:
        raise ValueError(
            "No subjects yet. Create one in the web UI (python main.py serve), "
            "or drop PDFs and assign them."
        )
    if subject:
        match = next((s for s in subs if subject in (s.slug, s.name)), None)
        if not match:
            avail = ", ".join(s.slug for s in subs)
            raise ValueError(f"Subject not found: {subject!r}. Available: {avail}")
        slug = match.slug
    else:
        slug = subs[0].slug
    return Library(settings.root, slug)


def cmd_ingest(args, settings, router) -> int:
    from agents.ingestion_agent import IngestionAgent

    agent = IngestionAgent(settings, router)
    lib = _library(settings, args.subject)
    agent.ingest_week(lib.week_dir(args.week), args.week)
    return 0


def cmd_explore(args, settings, router) -> int:
    from agents.web_explorer import WebExplorer

    lib = _library(settings, args.subject)
    agent = WebExplorer(settings, router)
    print(f"正在生成第 {args.week} 周知识结构图...")
    r = agent.enrich_week(lib.week_dir(args.week), args.week)
    print(f"✅ Wrote {r['path']}  ({r['count']} image(s) for: {', '.join(r['concepts'])})")
    return 0


def cmd_extension(args, settings, router) -> int:
    from agents.extension_agent import ExtensionAgent

    lib = _library(settings, args.subject)
    agent = ExtensionAgent(settings, router)
    out = agent.generate(lib.week_dir(args.week), args.week)
    print(f"✅ Wrote {out}")
    return 0


def cmd_quiz(args, settings, router) -> int:
    from agents.quiz_agent import QuizAgent

    agent = QuizAgent(settings, router)
    lib = _library(settings, args.subject)
    prior = list(range(1, args.week))
    print(f"📝 Building Week {args.week} quiz via {agent.engine}:{agent.model} "
          f"(interleaving from weeks {prior or 'none'}) …")
    r = agent.build_quiz(lib.week_dir(args.week), args.week, prior)
    print(f"✅ Wrote {r.quiz_path}")
    print(f"✅ Wrote {r.answers_path}  ← fill this in, then run `grade`")
    if r.interleaved:
        print("   Included an Interleaved Review section (~20% prior weeks).")
    return 0


def cmd_grade(args, settings, router) -> int:
    from agents.grader_agent import GraderAgent

    lib = _library(settings, args.subject)
    wdir = lib.week_dir(args.week)
    diagnostic = Diagnostic.open(lib.diagnostic_path())
    agent = GraderAgent(settings, router)
    print(f"🧭 Grading Week {args.week} via {agent.engine}:{agent.model} …\n")
    result = agent.grade(wdir / "Quiz.md", wdir / "Answers.md", args.week, diagnostic)
    print(result.feedback_markdown)
    print("\n" + "=" * 60)
    print(f"✅ Feedback written to {result.feedback_path}")
    print(f"✅ {len(result.findings)} finding(s) appended to {diagnostic.path}")
    return 0


def cmd_serve(args, settings, router) -> int:
    import uvicorn

    print(f"Agentic Study launcher on http://127.0.0.1:{args.port}  (Ctrl-C to stop)")
    uvicorn.run("webapp.server:app", host="127.0.0.1", port=args.port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agentic-study", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    def add_week(sp):
        sp.add_argument("--week", type=int, required=True, help="Week number, e.g. 1")
        sp.add_argument("--subject", help="Subject slug or name (default: first subject)")

    i = sub.add_parser("ingest", help="Phase 1: synthesize tiered notes (stub)")
    add_week(i)
    i.set_defaults(func=cmd_ingest)

    e = sub.add_parser("explore", help="Generate Mermaid knowledge diagrams")
    add_week(e)
    e.set_defaults(func=cmd_explore)

    x = sub.add_parser("extension", help="Phase 1: generate extension learning materials")
    add_week(x)
    x.set_defaults(func=cmd_extension)

    q = sub.add_parser("quiz", help="Phase 2: build a tiered quiz (+ Answers template)")
    add_week(q)
    q.set_defaults(func=cmd_quiz)

    g = sub.add_parser("grade", help="Phase 2: grade Answers.md (traced feedback)")
    add_week(g)
    g.set_defaults(func=cmd_grade)

    s = sub.add_parser("serve", help="Launch the browser study UI")
    s.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    s.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    router = make_router(settings)
    try:
        return args.func(args, settings, router)
    except LLMError as exc:
        print(f"\nLLM error: {exc}", file=sys.stderr)
        return 2
    except NotImplementedError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 3
    except (FileNotFoundError, ValueError) as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
