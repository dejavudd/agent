# -*- coding: utf-8 -*-
"""RAG integration layer.

Primary path: call a LightRAG Server over REST.
Fallback path: local lexical retrieval over generated notes and PDFs so the UI
remains usable before the external RAG service is configured.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import requests

from core.safety import build_safety_notice, check_text


class LightRAGClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.getenv("LIGHTRAG_BASE_URL") or "").rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("LIGHTRAG_API_KEY")

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def headers(self) -> dict[str, str]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        return headers

    def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"ok": False, "mode": "local", "message": "LIGHTRAG_BASE_URL not configured"}
        try:
            response = requests.get(f"{self.base_url}/health", headers=self.headers(), timeout=5)
            if response.ok:
                return {"ok": True, "mode": "lightrag", "status": response.status_code}
            return {"ok": False, "mode": "lightrag", "status": response.status_code}
        except requests.RequestException as exc:
            return {"ok": False, "mode": "local", "message": str(exc)}

    def query(self, question: str, mode: str = "mix") -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("LIGHTRAG_BASE_URL not configured")
        payload_variants = [
            {"query": question, "mode": mode},
            {"query": question, "param": {"mode": mode}},
            {"question": question, "mode": mode},
        ]
        last_error = ""
        for payload in payload_variants:
            try:
                response = requests.post(
                    f"{self.base_url}/query",
                    headers={**self.headers(), "Content-Type": "application/json"},
                    data=json.dumps(payload, ensure_ascii=False),
                    timeout=60,
                )
            except requests.RequestException as exc:
                last_error = str(exc)
                continue
            if response.ok:
                return _normalize_lightrag_response(response)
            last_error = f"{response.status_code} {response.text[:300]}"
        raise RuntimeError(f"LightRAG query failed: {last_error}")

    def upload_file(self, file_path: Path) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("LIGHTRAG_BASE_URL not configured")
        endpoints = ("/documents/upload", "/documents/file", "/upload")
        last_error = ""
        for endpoint in endpoints:
            try:
                with file_path.open("rb") as fh:
                    response = requests.post(
                        f"{self.base_url}{endpoint}",
                        headers=self.headers(),
                        files={"file": (file_path.name, fh)},
                        timeout=120,
                    )
            except requests.RequestException as exc:
                last_error = str(exc)
                continue
            if response.ok:
                return _json_or_text(response)
            last_error = f"{response.status_code} {response.text[:300]}"
        raise RuntimeError(f"LightRAG upload failed: {last_error}")

    def scan(self) -> dict[str, Any]:
        """Trigger the document processing pipeline."""
        if not self.configured:
            return {"ok": False}
        try:
            response = requests.post(
                f"{self.base_url}/documents/scan",
                headers=self.headers(), timeout=10
            )
            return _json_or_text(response) if response.ok else {"ok": False}
        except requests.RequestException:
            return {"ok": False}


def local_rag_answer(subject_dir: Path, question: str, router=None, agent_route=None) -> dict[str, Any]:
    chunks = build_local_index(subject_dir)
    hits = retrieve_chunks(chunks, question, k=5)
    context = "\n\n".join(
        f"[{i + 1}] {hit['source']}\n{hit['text']}" for i, hit in enumerate(hits)
    )
    synthesis_error = ""
    if router is not None and agent_route is not None and context.strip():
        prompt = (
            "Answer the student's question using only the course context below. "
            "If the answer is not in the context, say what is missing and suggest which material to index. "
            "Cite sources as [1], [2].\n\n"
            f"QUESTION:\n{question}\n\nCONTEXT:\n{context}"
        )
        try:
            answer = router.chat(
                [{"role": "user", "content": prompt}],
                engine=agent_route.engine,
                model=agent_route.model,
                temperature=agent_route.temperature,
                max_tokens=1800,
            )
        except Exception as exc:  # noqa: BLE001 - RAG must remain usable without an LLM key.
            synthesis_error = str(exc)
            answer = _extractive_answer(question, hits)
    else:
        answer = _extractive_answer(question, hits)
    safety = check_text(answer, context=context)
    notice = build_safety_notice(safety)
    if notice:
        answer = f"{notice}\n\n{answer}"
    result = {
        "mode": "local",
        "answer": answer,
        "sources": [{"source": h["source"], "score": h["score"]} for h in hits],
        "safety": safety.to_dict(),
    }
    if synthesis_error:
        result["synthesis_error"] = synthesis_error
    return result


def build_local_index(subject_dir: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in sorted(subject_dir.glob("Week_*/*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        if path.name in {"Answers.md"}:
            continue
        chunks.extend(_chunk_text(path.read_text(encoding="utf-8", errors="ignore"), path, subject_dir))
    for pdf in sorted(subject_dir.glob("Week_*/input/*.pdf")):
        chunks.extend(_chunk_text(_read_pdf_text(pdf), pdf, subject_dir))
    return chunks


def retrieve_chunks(chunks: list[dict[str, Any]], question: str, k: int = 5) -> list[dict[str, Any]]:
    q_tokens = _tokens(question)
    if not q_tokens:
        return chunks[:k]
    q_counter = Counter(q_tokens)
    scored = []
    for chunk in chunks:
        c_counter = Counter(chunk["tokens"])
        dot = sum(q_counter[t] * c_counter.get(t, 0) for t in q_counter)
        if not dot:
            continue
        denom = math.sqrt(sum(v * v for v in q_counter.values())) * math.sqrt(
            sum(v * v for v in c_counter.values())
        )
        score = dot / denom if denom else 0.0
        scored.append({**chunk, "score": round(score, 4)})
    return sorted(scored, key=lambda x: x["score"], reverse=True)[:k]


def _chunk_text(text: str, path: Path, subject_dir: Path, size: int = 900, overlap: int = 120) -> list[dict[str, Any]]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        part = text[start:start + size].strip()
        if part:
            chunks.append({
                "source": str(path.relative_to(subject_dir)),
                "text": part,
                "tokens": _tokens(part),
            })
        start += max(1, size - overlap)
    return chunks


def _read_pdf_text(path: Path) -> str:
    try:
        import fitz
    except ModuleNotFoundError:
        return ""
    try:
        doc = fitz.open(path)
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return ""


def _tokens(text: str) -> list[str]:
    text = text.lower()
    tokens: list[str] = []
    for seg in re.findall(r"[\w\u4e00-\u9fff]+", text):
        # ASCII words kept as-is; Chinese segments get unigram + bigram + trigram
        if re.search(r"[\u4e00-\u9fff]", seg):
            chars = list(seg)
            tokens.extend(chars)                                  # unigrams
            tokens.extend(a + b for a, b in zip(chars, chars[1:]))           # bigrams
            tokens.extend(a + b + c for a, b, c in zip(chars, chars[1:], chars[2:]))  # trigrams
        else:
            tokens.append(seg)
    return tokens


def _extractive_answer(question: str, hits: list[dict[str, Any]]) -> str:
    if not hits:
        return (
            "No relevant course content found for this question. "
            "Please generate notes first (click 'Ingest'), or upload more course materials."
        )
    lines = [
        "Most relevant course passages found below. Configure LLM API for a synthesized answer.",
        "",
    ]
    for i, hit in enumerate(hits, 1):
        lines.append(f"[{i}] {hit['source']} (score {hit['score']})")
        lines.append(hit["text"][:500])
        lines.append("")
    return "\n".join(lines).strip()


def _normalize_lightrag_response(response: requests.Response) -> dict[str, Any]:
    data = _json_or_text(response)
    if isinstance(data, dict):
        answer = data.get("response") or data.get("answer") or data.get("result") or str(data)
        return {"mode": "lightrag", "answer": answer, "raw": data}
    return {"mode": "lightrag", "answer": str(data), "raw": data}


def _json_or_text(response: requests.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
