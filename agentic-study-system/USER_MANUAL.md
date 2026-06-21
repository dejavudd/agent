# Agentic Study System — User Manual

*A field guide to how I actually run this thing. Written from the driver's seat, after a
semester of using it on my bilingual "Introduction to Computer Science" course.*

This isn't a spec — it's the workflow I've settled into. The short version: I drop a week's
lecture slides in, the system turns them into tiered notes, drills me with a quiz that grades
itself, then argues with me about my essay until my reasoning holds up. Everything is plain
Markdown on disk, so my whole study history is greppable and mine forever.

---

## 1. The mental model

Three things, nested:

- **Subject** → a course. Mine is *Introduction to Computer Science*. Lives in
  `curriculum/<slug>/`.
- **Week** → one topic's worth of slides inside a subject (`Week_NN/`). A week can hold more
  than one PDF deck.
- **Three phases** run on every week, in order:
  1. **Synthesis** — slides become tiered notes (Beginner / Intermediate / Advanced).
  2. **Retention** — a self-checking quiz + diagnostic feedback.
  3. **Review** — Socrates dismantles my essay; the Feynman pupil makes me teach it back.

Two "brains" do the work, and I almost never think about which:

- **The Heavy Lifter** — my self-hosted **gpt-oss-120b** on the tailab box (OpenAI-compatible
  vLLM). Does ingestion, quiz, grading, Socrates. Free, private, runs over my SSH tunnel.
- **The Fast Chatter** — a local **Ollama** model for the rapid Feynman back-and-forth.

The routing table is `config.yaml`. I never hard-code models anywhere else.

---

## 2. One-time setup

```bash
pip install -r requirements.txt          # includes pytesseract for slide OCR
brew install tesseract tesseract-lang     # the OCR binary + Korean language data
cp .env.example .env                       # then edit .env (git-ignored, never committed)
```

My `.env` points the Heavy Lifter at the tunnel:

```ini
API_PROVIDER=vllm
VLLM_BASE_URL=http://localhost:8006/v1
OLLAMA_HOST=http://localhost:11434
```

`API_PROVIDER` can also be `openai` or `anthropic` if I want a cloud model for a run (see
§7). The Feynman pupil needs no API key — it's pure Ollama.

**Bring the model up** (its own terminal, left running while I study):

```bash
scripts/tailab_tunnel.sh
```

That starts the `vllm-gpt-oss-120b` container on tailab if needed and holds the SSH tunnel
(`localhost:8006 → tailab:8006`). When I'm done for the day I stop the container with
`ssh tailab 'docker stop vllm-gpt-oss-120b'` to free the GPUs.

**Launch the app:**

```bash
python main.py serve            # → http://localhost:8000
```

The header shows `API: vllm · local: Ollama` so I always know which brain is wired in.

---

## 3. My weekly loop (the whole point)

Here's exactly what I do each week, in the web UI.

### Step 0 — Get the slides in
I drag the week's PDFs onto the **drop zone** (they land in the shared inbox), then use the
inbox checkboxes + **Assign → Week NN** to file them. A week can take several decks at once —
e.g. I once had a Programming Languages deck and a Computer Networks deck land in the same
week, and it handled both.

### Step 1 — Ingest (Synthesis)
Hit **Ingest** on the week. The system renders every page, **OCRs** the ones whose embedded
text is thin (my Korean slides are basically pictures of text — OCR is what makes them
legible), and then synthesizes **each deck separately** into three tier files:

- `Beginner.md` — broad strokes, real-world analogies, no machine internals.
- `Intermediate.md` — the *how*: process, application, worked transformations.
- `Advanced.md` — the nitty-gritty: hardware-level mechanics, deeper theory.

Because each deck is synthesized on its own, nothing gets dropped — a two-topic week comes
out with a clearly-labeled section per deck in every tier. Every tier carries a Mermaid
diagram, a worked example *before* any abstract rule, and the exact Korean term in
parentheses after each English term — those aren't suggestions, they're enforced in code and
re-prompted until they hold.

> This is the slow step (gpt-oss is a reasoning model, ~60 tok/s, and it writes a lot). I
> kick it off and go make coffee.

### Step 2 — Diagrams (optional dual-coding boost)
**Diagrams** pulls CC-licensed illustrations from Wikimedia Commons into the week's `assets/`
and writes `Diagrams.md`. Best-effort — if I'm offline, the inline Mermaid already covers me.

### Step 3 — Read the tiers
I open the week in the **Viewer** and read Beginner → Intermediate → Advanced. The Mermaid
flowcharts render inline. (They render reliably now — labels with Korean-in-parens are
auto-quoted before rendering, so nothing silently breaks.)

### Step 4 — Quiz (Retention)
**Quiz** generates a question bank sized in `config.yaml` (mine: ~20 Beginner, ~10
Intermediate, interleaved review from prior weeks, 3 Advanced essay prompts). The **Quiz tab**
is interactive:

- Multiple-choice and fill-in-the-blank get an **instant ✓/✗** when I hit *Check* — no waiting
  on the model. There's a running objective score and a *Check all* button.
- Definitions / application questions hide their answer until I hit *Reveal* — I self-grade
  against the model answer.
- The 3 essay prompts are just that — prompts. I pick one to write up.

When I want real feedback, **Submit for deeper feedback** sends my answers to the grader,
which writes `Feedback.md`. It never stamps "wrong" — it traces *where* my reasoning diverged,
and logs gaps to the subject's `Diagnostic.md`.

### Step 5 — Write the essay, then get torn apart (Review)
I write my synthesis essay into the **Advanced essay** box and save it (`Essay.md`).

- **Review** generates `Critique.md` — Socrates' opening attack on the essay's logic.
- **Debate** is the part I actually use: it opens a live chat where Socrates leads with that
  critique, I defend, and it rebuts my *defense* one point at a time. No grading — just relentless
  "where does that reasoning actually hold?" When I type `/done`, it appends a debate summary to
  `Diagnostic.md` (including which of its own attacks I successfully rebutted).

### Step 6 — Teach it back (Feynman)
**Feynman** opens a chat with a clueless-but-curious pupil running on local Ollama. It reads my
`Diagnostic.md`, picks my weakest spot, and makes me explain it in plain language, asking "why?"
until I either nail it or discover I can't. Fast, low-stakes, and brutal about jargon. `/done`
saves a session summary.

### Step 7 — Let the Diagnostic accumulate
`curriculum/<slug>/Diagnostic.md` is the system's memory of me — strengths, weaknesses, gaps,
and an append-only findings log fed by the grader, Socrates, and the pupil. Over weeks it
becomes a precise map of what I still don't understand. I skim it before exams.

---

## 4. Managing subjects & weeks

- **Subjects**: create / select / rename / delete from the top bar. Each subject has its own
  weeks and its own `Diagnostic.md`. The inbox is shared across subjects.
- **Weeks**: each week row has its actions plus **Edit** (rename, move/delete individual PDFs,
  merge into another week) and a direct **Delete** button (removes the whole week and its
  contents — there's a confirm; it's irreversible). Deleting leaves the other week numbers
  unchanged.

---

## 5. CLI equivalents

Everything in the UI has a command, same agents, no browser:

```bash
python main.py ingest  --week 3          # Synthesis (OCR + per-source tiers)
python main.py explore --week 3          # Wikimedia diagrams
python main.py quiz    --week 3          # generate Quiz.json + Quiz.md
python main.py grade   --week 3          # feedback on Answers.md
python main.py review  --week 3 [--essay PATH]   # Socratic critique
python main.py feynman --week 3 [--model M]      # teach-back loop (terminal)
```

Week commands take `--subject SLUG|NAME` (defaults to the first subject).

---

## 6. The files a week produces

```
curriculum/<slug>/Week_NN/
  input/            # the source PDFs (git-ignored)
  assets/           # rendered page images + downloaded diagrams (git-ignored)
  Beginner.md  Intermediate.md  Advanced.md     # tiered notes
  Diagrams.md       # Wikimedia illustrations
  Quiz.json         # the structured quiz + answer key (what the Quiz tab reads)
  Quiz.md           # human-readable, answer-free version
  Answers.md        # my submitted answers
  Feedback.md       # the grader's reasoning trace
  Essay.md          # my synthesis essay
  Critique.md       # Socrates' opening critique
curriculum/<slug>/Diagnostic.md               # evolving map of my understanding
```

---

## 7. Power moves & tuning

- **Make an agent tougher or cheaper**: edit only its entry in `config.yaml` (engine, model,
  temperature). Nothing else needs to change.
- **Resize the quiz**: `agents.quiz` keys `beginner / intermediate / interleaved / essays`.
- **Swap the brain for a run**: set `API_PROVIDER=openai` in `.env` to route the Heavy Lifter
  to a cloud model. I do this for **ingestion** when I want true *vision* on a deck — gpt-oss is
  text-only, so it reads slides via OCR; a vision model reads the images directly. Everything
  else I leave on gpt-oss.
- **OCR language**: `agents.ingestion.ocr_langs` (mine is `kor+eng`).
- **Tougher pupil**: point `feynman_pupil.model` at a bigger Ollama model.

---

## 8. Troubleshooting (things that bit me)

- **A diagram won't render** → it now shows a `⚠` with the raw source instead of blanking the
  page. Usually a stray Mermaid syntax issue; the common Korean-paren case is auto-fixed.
- **Ingestion / quiz feels slow** → that's gpt-oss-120b reasoning at ~60 tok/s, especially with
  the large quiz and per-deck synthesis. Normal. Shrink the quiz counts if I'm impatient.
- **"vLLM chat failed… is the tunnel open?"** → my tunnel or container dropped. Re-run
  `scripts/tailab_tunnel.sh`.
- **A whole topic missing from notes** → the deck's text layer was empty *and* OCR was off or
  Tesseract wasn't installed. Confirm `brew install tesseract tesseract-lang` and that
  `ocr: true` in config.
- **Networks/ingest looks thin** → re-ingest; the prompt now demands exhaustive,
  slide-grounded coverage rather than generic filler.

---

*That's the loop. Slides in on Monday, argued into submission by Friday, and a Diagnostic.md
that knows my weak spots better than I do.*
