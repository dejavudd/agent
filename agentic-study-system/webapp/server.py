"""FastAPI web server — the study launcher.

A thin HTTP layer over the existing agents and the Library. Long LLM calls run
in a worker thread (`asyncio.to_thread`) so the event loop stays responsive.
Designed for local single-user use.

Run with:  python main.py serve   (or: uvicorn webapp.server:app)
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.config import load_settings
from core.library import Library, SubjectStore, ensure_migrated
from core.llm_router import LLMError, make_router
from core.personalization import append_profile_signal, load_profile, save_profile
from core.rag_client import LightRAGClient, local_rag_answer
from core.recommendations import build_recommendations
from core.safety import build_safety_notice, check_text
from core.state import Diagnostic
from core.telemetry import behavior_summary, log_event

settings = load_settings()
router = make_router(settings)

ensure_migrated(settings.root)            # move any pre-subject layout into a default subject
subjects = SubjectStore(settings.root)
_active: dict[str, str | None] = {"subject": None}

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Agentic Study System")


def current_subject() -> str | None:
    """The active subject slug, defaulting to the first available one."""
    slugs = [s.slug for s in subjects.list_subjects()]
    if _active["subject"] not in slugs:
        _active["subject"] = slugs[0] if slugs else None
    return _active["subject"]


def get_library() -> Library:
    """Library scoped to the active subject (400 if none exists yet)."""
    slug = current_subject()
    if slug is None:
        raise HTTPException(400, "No subject yet. Create one first.")
    return Library(settings.root, slug)


def diagnostic() -> Diagnostic:
    return Diagnostic.open(get_library().diagnostic_path())


def _subject_name(slug: str | None = None) -> str:
    slug = slug or current_subject()
    for subject in subjects.list_subjects():
        if subject.slug == slug:
            return subject.name
    return slug or ""


def _subject_dir() -> Path:
    slug = current_subject()
    if slug is None:
        raise HTTPException(400, "No subject yet. Create one first.")
    return subjects.subject_dir(slug)


def _weeks_summary(lib: Library) -> str:
    lines = []
    for w in lib.list_weeks():
        bits = [
            f"Week {w.week:02d}",
            f"status={w.status}",
            f"title={w.title or '-'}",
            f"pdfs={len(w.pdfs)}",
            f"tiers={','.join(w.tiers) or '-'}",
            f"quiz={w.has_quiz}",
            f"feedback={w.has_feedback}",
            f"essay={w.has_essay}",
            ]
        lines.append(" | ".join(bits))
    return "\n".join(lines)


def _auto_profile_signal(signal: str, category: str) -> None:
    try:
        append_profile_signal(_subject_dir(), signal, category=category)
    except Exception:
        pass


def _route_for_optional_agent(name: str):
    try:
        return settings.route(name)
    except KeyError:
        return None


def _rag_indexable_files(week_dir: Path) -> list[Path]:
    """Collect the learning artifacts that are useful for grounded retrieval."""
    suffixes = {".pdf", ".md", ".txt", ".html"}
    patterns = ("input/*.pdf", "*.md", "generated_assets/*")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(
            path for path in week_dir.glob(pattern)
            if path.is_file() and path.suffix.lower() in suffixes
        )
    return sorted(files, key=lambda p: str(p.relative_to(week_dir)))


def _safe_name(name: str) -> str:
    """Reject path-traversal in a user-supplied filename; return it unchanged."""
    if not name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "Bad filename")
    return name


# --------------------------------------------------------------------- pages
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------------- state
@app.get("/api/state")
async def get_state() -> dict:
    slug = current_subject()
    lib = Library(settings.root, slug) if slug else None
    subject_dir = subjects.subject_dir(slug) if slug else None
    profile = load_profile(subject_dir) if subject_dir else {}
    weeks = [w.to_dict() for w in lib.list_weeks()] if lib else []
    return {
        "subjects": [s.to_dict() for s in subjects.list_subjects()],
        "subject": slug,
        "inbox": [],
        "weeks": weeks,
        "next_week": lib.next_week_number() if lib else 1,
        "api_provider": settings.api_provider,
        "rag": LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key).health(),
        "recommendations": build_recommendations(subject_dir, lib.list_weeks(), profile)
        if subject_dir and lib else [],
    }


# -------------------------------------------------------------------- subjects
@app.post("/api/subject/create")
async def subject_create(payload: dict) -> dict:
    try:
        slug = subjects.create_subject(str(payload.get("name", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    _active["subject"] = slug
    return {"slug": slug, "name": str(payload.get("name", "")).strip()}


@app.post("/api/subject/select")
async def subject_select(payload: dict) -> dict:
    slug = str(payload.get("slug", ""))
    if not subjects.exists(slug):
        raise HTTPException(404, f"Subject not found: {slug}")
    _active["subject"] = slug
    return {"slug": slug}


@app.post("/api/subject/rename")
async def subject_rename(payload: dict) -> dict:
    slug = str(payload["slug"])
    try:
        name = subjects.rename_subject(slug, str(payload.get("name", "")))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"slug": slug, "name": name}


@app.post("/api/subject/delete")
async def subject_delete(payload: dict) -> dict:
    slug = str(payload["slug"])
    try:
        subjects.delete_subject(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    if _active["subject"] == slug:
        _active["subject"] = None
    return {"deleted": slug}


@app.get("/api/diagnostic", response_class=PlainTextResponse)
async def get_diagnostic() -> str:
    return diagnostic().read()


@app.get("/api/profile")
async def get_profile() -> dict:
    subject_dir = _subject_dir()
    profile = load_profile(subject_dir)
    return {
        "profile": profile,
        "markdown": (subject_dir / "Profile.md").read_text(encoding="utf-8"),
    }


@app.get("/api/behavior", response_class=PlainTextResponse)
async def get_behavior_summary() -> str:
    return behavior_summary(_subject_dir())


@app.post("/api/behavior")
async def behavior(payload: dict) -> dict:
    event = log_event(_subject_dir(), str(payload.get("type", "ui_event")), payload.get("payload") or {})
    return {"event": event}


@app.post("/api/profile/save")
async def profile_save(payload: dict) -> dict:
    subject_dir = _subject_dir()
    profile = save_profile(subject_dir, payload.get("profile") or {})
    return {
        "profile": profile,
        "markdown": (subject_dir / "Profile.md").read_text(encoding="utf-8"),
    }


@app.post("/api/profile/build")
async def profile_build(payload: dict) -> JSONResponse:
    from agents.profile_agent import ProfileAgent

    subject_dir = _subject_dir()
    lib = get_library()
    agent = ProfileAgent(settings, router)
    try:
        profile = await asyncio.to_thread(
            agent.build,
            current_profile=load_profile(subject_dir),
            interview_notes=str(payload.get("notes", "")),
            diagnostic_text=diagnostic().read(),
            subject_name=_subject_name(),
            weeks_summary=_weeks_summary(lib),
        )
        saved = save_profile(subject_dir, profile)
    except LLMError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    return JSONResponse({
        "profile": saved,
        "markdown": (subject_dir / "Profile.md").read_text(encoding="utf-8"),
        "file": "Profile.md",
    })


@app.get("/api/week/{week}/file/{name}", response_class=PlainTextResponse)
async def get_week_file(week: int, name: str) -> str:
    # Guard against path traversal; only allow plain filenames.
    _safe_name(name)
    path = get_library().week_dir(week) / name
    if not path.exists():
        raise HTTPException(404, f"{name} not found for Week {week:02d}")
    return path.read_text(encoding="utf-8")


@app.get("/api/week/{week}/asset/{name}")
async def get_week_asset(week: int, name: str) -> FileResponse:
    """Serve a downloaded image from a week's assets/ (so Diagrams.md renders)."""
    _safe_name(name)
    path = get_library().week_dir(week) / "assets" / name
    if not path.exists():
        raise HTTPException(404, f"asset {name} not found for Week {week:02d}")
    return FileResponse(path)


@app.get("/api/week/{week}/generated/{name}")
async def get_generated_asset(week: int, name: str) -> FileResponse:
    _safe_name(name)
    path = get_library().week_dir(week) / "generated_assets" / name
    if not path.exists():
        raise HTTPException(404, f"generated asset {name} not found for Week {week:02d}")
    return FileResponse(path)


# --------------------------------------------------------------------- upload
@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), week: str = Form("inbox")) -> dict:
    """Save PDFs directly into a new or existing week's input/ directory."""
    if week == "new":
        lib = get_library()
        target_week = lib.next_week_number()
        dest_dir = lib.create_week(target_week) / "input"
    elif week.isdigit():
        target_week = int(week)
        dest_dir = get_library().create_week(target_week) / "input"
    else:
        raise HTTPException(400, "Uploads must target a new or existing learning unit.")

    saved = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            continue
        dest = dest_dir / Path(f.filename).name
        dest.write_bytes(await f.read())
        saved.append(dest.name)
    return {"saved": saved, "week": target_week}


# ------------------------------------------------------------------ pipeline
@app.post("/api/ingest")
async def ingest(payload: dict) -> JSONResponse:
    from agents.ingestion_agent import IngestionAgent

    week = int(payload["week"])
    agent = IngestionAgent(settings, router)
    try:
        outputs = await asyncio.to_thread(
            agent.ingest_week, get_library().week_dir(week), week
        )
    except LLMError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    log_event(_subject_dir(), "ingest", {"week": week, "files": [p.name for p in outputs.values()]})
    _auto_profile_signal(f"Week {week:02d} materials were ingested into tiered notes.", "study")
    return JSONResponse({
        "week": week,
        "tiers": {t: p.name for t, p in outputs.items()},
    })


@app.get("/api/ingest/stream")
async def ingest_stream(week: int) -> StreamingResponse:
    """SSE endpoint: streams per-tier progress during ingest."""
    import json as _json
    from agents.ingestion_agent import IngestionAgent

    queue: asyncio.Queue = asyncio.Queue()

    def _run():
        from core.pdf_parser import parse_week_inputs
        from agents.ingestion_agent import TIERS

        agent = IngestionAgent(settings, router)
        lib = get_library()
        week_dir = lib.week_dir(week)

        try:
            queue.put_nowait({"type": "step", "msg": "正在解析 PDF..."})
            parsed = parse_week_inputs(
                week_dir / "input",
                week_dir / "assets",
                ocr=agent.ocr,
                ocr_langs=agent.ocr_langs,
                ocr_min_chars=agent.ocr_min_chars,
            )
            if not parsed:
                raise FileNotFoundError(f"No PDFs in {week_dir / 'input'}.")

            tier_labels = {"Beginner": "基础", "Intermediate": "进阶", "Advanced": "拓展"}
            outputs = {}
            for tier, guidance in TIERS.items():
                queue.put_nowait({"type": "step", "msg": f"正在生成{tier_labels.get(tier, tier)}讲义..."})
                system = (
                    agent.system_prompt
                    .replace("{{TIER}}", tier)
                    .replace("{{TIER_GUIDANCE}}", guidance)
                )
                sections = [
                    agent._synthesize_source(system, tier, week, pdf)
                    for pdf in parsed if pdf.full_text.strip()
                ]
                out_path = week_dir / f"{tier}.md"
                out_path.write_text(agent._assemble(tier, week, sections), encoding="utf-8")
                outputs[tier] = out_path
                queue.put_nowait({"type": "tier_done", "tier": tier, "file": out_path.name})

            log_event(_subject_dir(), "ingest", {"week": week, "files": [p.name for p in outputs.values()]})
            _auto_profile_signal(f"Week {week:02d} materials were ingested into tiered notes.", "study")
            queue.put_nowait({"type": "done", "tiers": {t: p.name for t, p in outputs.items()}})
        except Exception as exc:
            queue.put_nowait({"type": "error", "msg": str(exc)})

    async def _generate():
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _run)
        yield "retry: 1000\n\n"
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=180)
            except asyncio.TimeoutError:
                yield "event: error\ndata: {\"msg\": \"超时，请重试\"}\n\n"
                break
            event = item.get("type", "message")
            yield f"event: {event}\ndata: {_json.dumps(item, ensure_ascii=False)}\n\n"
            if event in ("done", "error"):
                break

    return StreamingResponse(_generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@app.post("/api/quiz")
async def quiz(payload: dict) -> JSONResponse:
    from agents.quiz_agent import QuizAgent

    week = int(payload["week"])
    agent = QuizAgent(settings, router)
    prior = list(range(1, week))
    try:
        result = await asyncio.to_thread(
            agent.build_quiz, get_library().week_dir(week), week, prior
        )
    except LLMError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    log_event(_subject_dir(), "quiz_generated", {"week": week, "file": result.quiz_path.name})
    _auto_profile_signal(f"Week {week:02d} quiz was generated for retention practice.", "study")
    return JSONResponse({
        "week": week,
        "quiz": result.quiz_path.name,
        "spec": result.spec_path.name,
        "answers": result.answers_path.name,
        "interleaved": result.interleaved,
    })


@app.post("/api/explore")
async def explore(payload: dict) -> JSONResponse:
    from agents.web_explorer import WebExplorer

    week = int(payload["week"])
    agent = WebExplorer(settings, router)
    try:
        result = await asyncio.to_thread(
            agent.enrich_week, get_library().week_dir(week), week
        )
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    log_event(_subject_dir(), "diagrams", {"week": week, "count": result["count"]})
    return JSONResponse({
        "week": week,
        "file": result["path"].name,
        "count": result["count"],
        "concepts": result["concepts"],
    })


@app.post("/api/extension")
async def extension(payload: dict) -> JSONResponse:
    from agents.extension_agent import ExtensionAgent

    week = int(payload["week"])
    agent = ExtensionAgent(settings, router)
    try:
        out = await asyncio.to_thread(agent.generate, get_library().week_dir(week), week)
    except LLMError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    log_event(_subject_dir(), "extension_generated", {"week": week, "file": out.name})
    _auto_profile_signal(f"Week {week:02d} extension materials were generated.", "resource")
    return JSONResponse({"week": week, "file": out.name})


@app.post("/api/path")
async def path_plan() -> JSONResponse:
    from agents.path_planner import PathPlannerAgent

    lib = get_library()
    subject_dir = _subject_dir()
    agent = PathPlannerAgent(settings, router)
    try:
        out = await asyncio.to_thread(
            agent.plan,
            subject_dir=subject_dir,
            subject_name=_subject_name(),
            profile_markdown=(subject_dir / "Profile.md").read_text(encoding="utf-8")
            if (subject_dir / "Profile.md").exists() else "",
            diagnostic_text=diagnostic().read(),
            weeks_summary=_weeks_summary(lib),
        )
    except LLMError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    log_event(_subject_dir(), "path_generated", {"file": out.name})
    return JSONResponse({"file": out.name})


@app.get("/api/path", response_class=PlainTextResponse)
async def path_get() -> str:
    path = _subject_dir() / "LearningPath.md"
    if not path.exists():
        raise HTTPException(404, "LearningPath.md not found. Generate the path first.")
    return path.read_text(encoding="utf-8")


@app.post("/api/safety/check")
async def safety_check(payload: dict) -> dict:
    result = check_text(str(payload.get("text", "")), context=str(payload.get("context", "")))
    return {"result": result.to_dict(), "notice": build_safety_notice(result)}


@app.post("/api/rag/ask")
async def rag_ask(payload: dict) -> JSONResponse:
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty.")
    mode = str(payload.get("mode") or settings.lightrag_default_mode or "mix")
    client = LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key)
    try:
        if client.configured:
            result = await asyncio.to_thread(client.query, question, mode)
            safety = check_text(str(result.get("answer", "")))
            if not safety.ok:
                result["answer"] = f"{build_safety_notice(safety)}\n\n{result.get('answer', '')}"
                result["safety"] = safety.to_dict()
        else:
            route = _route_for_optional_agent("rag_tutor")
            result = await asyncio.to_thread(
                local_rag_answer, _subject_dir(), question, router, route
            )
    except Exception as exc:
        route = _route_for_optional_agent("rag_tutor")
        result = await asyncio.to_thread(
            local_rag_answer, _subject_dir(), question, router, route
        )
        result["fallback_reason"] = str(exc)
    log_event(_subject_dir(), "rag_ask", {"question": question[:200], "mode": result.get("mode")})
    _auto_profile_signal(f"Asked grounded RAG tutoring question: {question[:160]}", "rag")
    return JSONResponse(result)


@app.get("/api/rag/status")
async def rag_status() -> JSONResponse:
    """Return LightRAG document processing status summary."""
    client = LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key)
    if not client.configured:
        return JSONResponse({"configured": False})
    try:
        resp = await asyncio.to_thread(
            lambda: __import__("requests").get(
                f"{client.base_url}/documents", headers=client.headers(), timeout=5
            )
        )
        if not resp.ok:
            return JSONResponse({"configured": True, "error": resp.status_code})
        statuses = (resp.json().get("statuses") or {})
        return JSONResponse({
            "configured": True,
            "pending":    len(statuses.get("pending", []) or []),
            "processing": len(statuses.get("processing", []) or []),
            "processed":  len(statuses.get("processed", []) or []),
            "failed":     len(statuses.get("failed", []) or []),
        })
    except Exception as exc:
        return JSONResponse({"configured": True, "error": str(exc)})


@app.post("/api/rag/index-week")
async def rag_index_week(payload: dict) -> JSONResponse:
    """Index all generated notes for the active subject (week param ignored)."""
    client = LightRAGClient(settings.lightrag_base_url, settings.lightrag_api_key)
    if not client.configured:
        return JSONResponse({
            "mode": "local",
            "message": "LightRAG 未配置，系统将按需使用本地课程资料检索。",
        })
    lib = get_library()
    files: list[Path] = []
    for w in lib.list_weeks():
        files.extend(_rag_indexable_files(lib.week_dir(w.week)))
    uploaded, errors = [], []
    for path in files:
        try:
            uploaded.append({"file": path.name, "result": await asyncio.to_thread(client.upload_file, path)})
        except Exception as exc:
            errors.append({"file": path.name, "error": str(exc)})
    if uploaded:
        await asyncio.to_thread(client.scan)
    log_event(_subject_dir(), "rag_index_subject", {"uploaded": len(uploaded), "errors": len(errors)})
    return JSONResponse({"mode": "lightrag", "uploaded": uploaded, "errors": errors})


# Files the student is allowed to write through the UI.
_SAVABLE = {"Answers.md", "Essay.md"}


@app.post("/api/save")
async def save_file(payload: dict) -> JSONResponse:
    week = int(payload["week"])
    name = str(payload["name"])
    if name not in _SAVABLE:
        raise HTTPException(400, f"Cannot save {name!r}; allowed: {sorted(_SAVABLE)}")
    path = get_library().create_week(week) / name
    path.write_text(payload.get("content", ""), encoding="utf-8")
    log_event(_subject_dir(), "file_saved", {"week": week, "file": name})
    if name == "Answers.md":
        _auto_profile_signal(f"Week {week:02d} quiz answers were submitted/saved.", "grade")
    elif name == "Essay.md":
        _auto_profile_signal(f"Week {week:02d} advanced essay was saved.", "study")
    return JSONResponse({"week": week, "saved": name})


@app.post("/api/grade")
async def grade(payload: dict) -> JSONResponse:
    from agents.grader_agent import GraderAgent

    week = int(payload["week"])
    wdir = get_library().week_dir(week)
    agent = GraderAgent(settings, router)
    try:
        result = await asyncio.to_thread(
            agent.grade, wdir / "Quiz.md", wdir / "Answers.md", week, diagnostic()
        )
    except LLMError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    except (FileNotFoundError, ValueError) as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    log_event(_subject_dir(), "graded", {"week": week, "findings": result.findings})
    _auto_profile_signal(
        f"Week {week:02d} grading generated {len(result.findings)} diagnostic findings.",
        "grade",
    )
    return JSONResponse({
        "week": week,
        "feedback": result.feedback_markdown,
        "findings": result.findings,
        "file": result.feedback_path.name,
    })

# Mount static assets last so /api takes precedence.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
