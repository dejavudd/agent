# CLAUDE.md — Agentic Study System

Persistent project context for future agentic sessions. Read this first.

## What this is
A local, multi-agent "Agentic Study System" that ingests a bilingual (English/Korean)
"Introduction to Computer Science" curriculum and runs it through three pedagogical phases:
Synthesis → Retention → Review. State and study materials are plain Markdown.

## Hybrid LLM routing (deterministic table)
The router table lives in **`config.yaml`**; never hard-code models in agents.

| Logical engine | Resolves to | Role | Used by |
|----------------|-------------|------|---------|
| `api` | Anthropic, OpenAI, **or** `vllm` (set by `API_PROVIDER` in `.env`) | Heavy Lifter — large context, EN/KO translation, vision for slides¹ | ingestion, web_explorer, quiz, grader, **socratic_dismantler** |
| `ollama` | local model named in `config.yaml` (default `qwen2.5:7b`) | Fast Chatter — low-latency conversational loops | **feynman_pupil** |

¹ `vllm` = a self-hosted, OpenAI-compatible server (the **tailab** gpt-oss box). It is
**text-only**: under `API_PROVIDER=vllm`, ingestion's slide page-images are dropped (Mermaid
still covers Dual Coding). Reach it via `scripts/tailab_tunnel.sh` (forwards `localhost:8006` →
the remote container; served-model-name `gpt-oss-120b`). Default model per provider is set in
`config.yaml:api_models`.

- All model calls go through `core/llm_router.py::LLMRouter.chat(...)`. Add backends there.
- `core/config.py` resolves the logical `api` engine into a concrete provider + model.
- To make an agent tougher/cheaper, edit only its `config.yaml` entry (engine/model/temperature).

## API key & environment structure
Copy `.env.example` → `.env` (git-ignored) and set:

| Var | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY` | Claude access (if `API_PROVIDER=anthropic`) |
| `OPENAI_API_KEY` | GPT access (if `API_PROVIDER=openai`) |
| `API_PROVIDER` | `anthropic` \| `openai` \| `vllm` — which provider the `api` engine uses |
| `VLLM_BASE_URL` | OpenAI-compatible endpoint (if `API_PROVIDER=vllm`; default `http://localhost:8006/v1`, via the tailab SSH tunnel) |
| `VLLM_API_KEY` | Dummy token for vLLM (default `EMPTY`; vLLM ignores it unless started with `--api-key`) |
| `OLLAMA_HOST` | Ollama endpoint (default `http://localhost:11434`) |

The Feynman Pupil runs fully offline on Ollama and needs **no** API key.

## Pedagogical invariants (enforced, not hoped for)
These are checked in code by `core/validators.py` and re-prompted via
`BaseAgent.run_validated`. Do not weaken them.
1. **Cognitive Load** — broad concepts vs hardware specifics live in separate tier files
   (`Beginner.md` / `Intermediate.md` / `Advanced.md`).
2. **Dual Coding** — every synthesis file contains at least one `mermaid` diagram
   (`has_mermaid_block`).
3. **Worked-Example Effect** — a solved step-by-step example precedes any abstract rule
   (`worked_example_before_rules`).
4. **Bilingual Integrity** — output is English; the exact Korean term sits in parentheses
   right after the English term, e.g. `binary (이진법)` (`korean_in_parentheses`).
5. **Metacognitive Scaffolding** — never "Correct/Incorrect"; trace where the mental model
   broke down (`no_binary_grading`).

## Interfaces
- **Web launcher** (`python main.py serve`, default port 8000): FastAPI app in `webapp/`.
  Drop PDFs → inbox (`study/inbox/`) → "Study → Week NN" assigns them → per-week Ingest / Quiz /
  Review / Debate / Feynman buttons (Quiz tab is an interactive auto-checked quiz). Long LLM calls
  run via `asyncio.to_thread`; the Feynman teach-back and the Socratic debate are WebSockets
  (`/ws/feynman/{week}`, `/ws/socrates/{week}`), sharing one "Live Chat" panel. Frontend is
  dependency-free vanilla JS in `webapp/static/`.
- **CLI** (`python main.py <cmd>`): same agents, no browser.

## Workflow
1. **Phase 1 — Synthesis** (`ingest --week N` / Ingest button): parse `Week_NN/input/*.pdf` →
   three tiered notes. These decks are image-based (near-empty text layers), so `core/pdf_parser.py`
   renders each page and **OCRs** (Tesseract `kor+eng`, via `core/ocr.py`) any page whose embedded
   text is sparser than `ocr_min_chars`. Each source PDF is synthesized **separately** and the
   per-source sections are concatenated into each tier file, so a week holding two different topics
   never drops one. Requires the Tesseract binary + Korean data (`brew install tesseract
   tesseract-lang`). Under text-only gpt-oss there is no slide *vision* — OCR is what makes the
   slides legible; a vision provider (`API_PROVIDER=openai`) remains an option. **Implemented.**
   `explore --week N` / the **Diagrams** button runs the Web Explorer: it picks diagram queries
   from the notes (LLM, with a heading fallback) and pulls CC-licensed images from **Wikimedia
   Commons** into `assets/`, writing `Diagrams.md`. Best-effort — Mermaid still covers Dual Coding
   if offline. **Implemented.**
2. **Phase 2 — Retention** (`quiz --week N`, then `grade --week N` / Quiz tab): tiered quiz
   (MCQ/cloze → application/logic → essay prompts) plus an interleaved review section from prior
   weeks. Per-tier counts live in `config.yaml:agents.quiz` (`beginner`/`intermediate`/
   `interleaved`/`essays`) — the prompt format is a template, not a quantity. The model returns a
   structured JSON question bank **with answer keys**, validated by `valid_quiz_json`
   (`core/validators.py`); the agent writes `Quiz.json` (authoritative), an **answer-free**
   `Quiz.md` (Viewer/markdown compat), and a blank `Answers.md`. The **Quiz tab is interactive**:
   it reads `Quiz.json` and gives an instant, deterministic ✓/✗ self-check for MCQ + cloze
   (client-side, offline); definitions/application/logic reveal a model answer; essays are prompts
   only (→ Phase 3). "Submit for deeper feedback" assembles `Answers.md` and runs the grader, which
   writes `Feedback.md` tracing where reasoning diverges (never binary-grades — invariant #5 holds
   on the grader path) and logs findings to `Diagnostic.md`. **Implemented.**
3. **Phase 3 — Review** (implemented):
   - **Agent A** `review --week N [--essay PATH]` — Socratic Dismantler attacks the Advanced
     essay, writes `Critique.md`, appends flaws to the subject's `Diagnostic.md`. It is also a
     **live debater**: the **Debate** button opens a WebSocket (`/ws/socrates/{week}`) that reads
     `Essay.md` + `Critique.md` (auto-generating the critique if missing), sends the critique as
     its opening message, then rebuts the student's defenses one point at a time using a separate
     `prompts/socratic_debate.md` persona (still no binary grading). On `/done` it appends a debate
     summary to `Diagnostic.md`.
   - **Agent B** `feynman --week N [--model M]` — Feynman Pupil reads `Diagnostic.md` and runs a
     teach-back loop (terminal or WebSocket `/ws/feynman/{week}`); appends a session summary.

## Subjects (top-level grouping)
Weeks live under a **subject**: `curriculum/<slug>/Week_NN/`. A subject folder holds a
`subject.json` ({"name": ...}; the slug folder name never changes on rename) and its own
`Diagnostic.md`. `core/library.py` splits this into `Library` (scoped to one subject, via
`Library(root, slug)`) and `SubjectStore` (list/create/rename/delete subjects).
`ensure_migrated()` runs at server/CLI startup and folds any legacy flat `curriculum/Week_NN/`
(+ old `state/Diagnostic.md`) into a default subject — idempotent. The inbox is **shared** across
subjects. The web server tracks one active subject (`/api/subject/{create,select,rename,delete}`);
CLI week commands take `--subject SLUG|NAME` (default: first subject).

## State files
- `curriculum/<slug>/Diagnostic.md` — per-subject evolving strengths/weaknesses/gaps +
  append-only Findings Log. Shared memory between Agent A and Agent B; auto-created from template.
- `curriculum/<slug>/Week_NN/` — per-week `input/`, tier notes, `assets/`, `Quiz.json` (+ rendered
  `Quiz.md`), `Answers.md`, `Feedback.md`, `Essay.md`, `Critique.md`, plus a `meta.json` for the
  optional week display title.

## Context discipline
Agents are independent and exchange **file paths + short summaries**, never raw essays/slides,
so the orchestrator's context window stays small. Keep it that way when extending.

## Layout
```
core/      config, llm_router (multimodal), base_agent, validators, pdf_parser, state, library
agents/    ingestion, web_explorer (Commons diagrams), quiz, grader, socratic_dismantler, feynman_pupil
prompts/   per-agent system prompts (rules encoded in prose)
webapp/    server.py (FastAPI) + static/ (index.html, app.js, style.css)
study/inbox/                   shared drop-zone for new PDFs
curriculum/<slug>/             one subject: subject.json + Diagnostic.md + weeks
curriculum/<slug>/Week_NN/     per-week inputs & outputs (+ meta.json title)
config.yaml  routing table   ·   main.py  CLI + `serve`
```

## Conventions for future edits
- New agent → add a `config.yaml` entry, subclass `BaseAgent`, put rules in a `prompts/*.md`.
- New rule → add a `Validator` in `core/validators.py` and include it in the agent's bundle.
- New backend → extend `LLMRouter.chat`; keep the uniform `(messages, engine, model, system,
  temperature)` signature.
