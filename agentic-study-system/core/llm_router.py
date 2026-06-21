"""Hybrid LLM router — the single choke point for every model call.

One uniform `chat()` signature dispatches to four backends:

    * anthropic  -> cloud "Heavy Lifter"  (Claude)
    * openai     -> cloud "Heavy Lifter"  (GPT)
    * vllm       -> self-hosted "Heavy Lifter" (OpenAI-compatible, e.g. gpt-oss on tailab)
    * ollama     -> local "Fast Chatter"  (qwen, etc.)

SDKs are imported lazily so the project installs/runs even if you only use one
backend. Errors are actionable: a missing key or a down Ollama server tells you
exactly what to fix rather than throwing a deep SDK traceback.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Iterable

from core.config import Settings

# A message is a plain dict: {"role": "user"|"assistant", "content": str}.
# It may optionally carry {"images": [Path|str, ...]} for vision-capable engines
# (used by Phase 1 ingestion to send slide page-images alongside the text).
Message = dict[str, Any]

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def _encode_image(path: Path | str) -> tuple[str, str]:
    """Return (base64_data, media_type) for an image file."""
    p = Path(path)
    media = _MEDIA_TYPES.get(p.suffix.lower(), "image/png")
    return base64.b64encode(p.read_bytes()).decode("ascii"), media


def _api_error_hint(provider: str, exc: Exception) -> str:
    """Turn a raw SDK exception into an actionable one-liner."""
    msg = str(exc).lower()
    portal = ("platform.openai.com/account/billing" if provider == "OpenAI"
              else "console.anthropic.com")
    if "insufficient_quota" in msg or "exceeded your current quota" in msg:
        return (f"{provider} account has no available quota/credits. "
                f"Add billing at {portal}, then retry.")
    if "rate limit" in msg or "429" in msg:
        return f"{provider} rate limit hit. Wait a moment and retry."
    if "invalid_api_key" in msg or "incorrect api key" in msg or "401" in msg \
            or "authentication" in msg:
        return (
            f"{provider} API key is invalid. Check the key in .env. "
            "If you are using a third-party OpenAI-compatible service, also set "
            "OPENAI_BASE_URL to that service's /v1 endpoint."
        )
    if "model" in msg and ("not found" in msg or "does not exist" in msg):
        return f"{provider} model not available to this account. Pick another in config.yaml."
    return f"{provider} API error: {exc}"


class LLMError(RuntimeError):
    """Raised for configuration / connectivity problems with a fix hint."""


class LLMRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Clients are created on first use and cached here.
        self._anthropic = None
        self._openai = None
        self._vllm = None
        self._ollama = None

    # ------------------------------------------------------------------ public
    def chat(
        self,
        messages: Iterable[Message],
        *,
        engine: str,
        model: str,
        system: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion and return the assistant text.

        `engine` is concrete ("anthropic" | "openai" | "vllm" | "ollama") — the
        logical "api" alias is already resolved in core.config.
        """
        messages = list(messages)
        if engine == "anthropic":
            return self._chat_anthropic(messages, model, system, temperature, max_tokens)
        if engine == "openai":
            return self._chat_openai(messages, model, system, temperature, max_tokens)
        if engine == "vllm":
            return self._chat_vllm(messages, model, system, temperature, max_tokens)
        if engine == "ollama":
            return self._chat_ollama(messages, model, system, temperature)
        raise LLMError(f"Unknown engine '{engine}'.")

    # --------------------------------------------------------------- anthropic
    def _chat_anthropic(self, messages, model, system, temperature, max_tokens) -> str:
        if not self.settings.anthropic_api_key:
            raise LLMError(
                "ANTHROPIC_API_KEY is not set. Add it to .env "
                "(or switch API_PROVIDER=openai)."
            )
        if self._anthropic is None:
            try:
                import anthropic
            except ModuleNotFoundError as exc:
                raise LLMError(
                    "The 'anthropic' package is not installed. "
                    "Run: pip install -r requirements.txt"
                ) from exc
            self._anthropic = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)

        try:
            resp = self._anthropic.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system or "",
                messages=self._to_anthropic(messages),
            )
        except Exception as exc:  # noqa: BLE001 - surface a clean hint
            raise LLMError(_api_error_hint("Anthropic", exc)) from exc
        return "".join(block.text for block in resp.content if block.type == "text")

    @staticmethod
    def _to_anthropic(messages: list[Message]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            images = m.get("images")
            if not images:
                out.append({"role": m["role"], "content": m["content"]})
                continue
            blocks: list[dict] = [{"type": "text", "text": m["content"]}]
            for img in images:
                data, media = _encode_image(img)
                blocks.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media, "data": data},
                })
            out.append({"role": m["role"], "content": blocks})
        return out

    # ------------------------------------------------------------------ openai
    def _chat_openai(self, messages, model, system, temperature, max_tokens) -> str:
        if not self.settings.openai_api_key:
            raise LLMError(
                "OPENAI_API_KEY is not set. Add it to .env "
                "(or switch API_PROVIDER=anthropic)."
            )
        if self._openai is None:
            try:
                import openai
            except ModuleNotFoundError as exc:
                raise LLMError(
                    "The 'openai' package is not installed. "
                    "Run: pip install -r requirements.txt"
                ) from exc
            client_kwargs = {"api_key": self.settings.openai_api_key}
            if self.settings.openai_base_url:
                client_kwargs["base_url"] = self.settings.openai_base_url
            self._openai = openai.OpenAI(**client_kwargs)

        # OpenAI carries the system prompt as the first message.
        full = ([{"role": "system", "content": system}] if system else []) \
            + self._to_openai(messages)
        try:
            resp = self._openai.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=full,
            )
        except Exception as exc:  # noqa: BLE001 - surface a clean hint
            raise LLMError(_api_error_hint("OpenAI", exc)) from exc
        return resp.choices[0].message.content or ""

    @staticmethod
    def _to_openai(messages: list[Message]) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            images = m.get("images")
            if not images:
                out.append({"role": m["role"], "content": m["content"]})
                continue
            parts: list[dict] = [{"type": "text", "text": m["content"]}]
            for img in images:
                data, media = _encode_image(img)
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{media};base64,{data}"},
                })
            out.append({"role": m["role"], "content": parts})
        return out

    # -------------------------------------------------------------------- vllm
    def _chat_vllm(self, messages, model, system, temperature, max_tokens) -> str:
        """Self-hosted, OpenAI-compatible endpoint (e.g. gpt-oss served by vLLM).

        Reuses the OpenAI SDK pointed at `vllm_base_url`. gpt-oss is text-only,
        so any image attachments are dropped (with an inline note) rather than
        sent as `image_url` parts the server would reject.
        """
        if self._vllm is None:
            try:
                import openai
            except ModuleNotFoundError as exc:
                raise LLMError(
                    "The 'openai' package is not installed (required for the vLLM "
                    "backend too). Run: pip install -r requirements.txt"
                ) from exc
            self._vllm = openai.OpenAI(
                base_url=self.settings.vllm_base_url,
                api_key=self.settings.vllm_api_key or "EMPTY",
            )

        full = ([{"role": "system", "content": system}] if system else []) \
            + self._to_text_only(messages)
        try:
            resp = self._vllm.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=full,
            )
        except Exception as exc:  # noqa: BLE001 - surface a clean hint
            raise LLMError(
                f"vLLM chat failed for model '{model}' at "
                f"{self.settings.vllm_base_url}: {exc}. Is the SSH tunnel open "
                f"and the container running? (see scripts/tailab_tunnel.sh)"
            ) from exc
        return resp.choices[0].message.content or ""

    @staticmethod
    def _to_text_only(messages: list[Message]) -> list[dict]:
        """Flatten messages to plain text, noting any dropped images."""
        out: list[dict] = []
        for m in messages:
            content = m["content"]
            n = len(m.get("images") or [])
            if n:
                content = f"{content}\n\n[{n} image(s) omitted: this model is text-only.]"
            out.append({"role": m["role"], "content": content})
        return out

    # ------------------------------------------------------------------ ollama
    def _chat_ollama(self, messages, model, system, temperature) -> str:
        try:
            import ollama
        except ModuleNotFoundError as exc:
            raise LLMError(
                "The 'ollama' package is not installed. "
                "Run: pip install -r requirements.txt"
            ) from exc
        if self._ollama is None:
            self._ollama = ollama.Client(host=self.settings.ollama_host)
            self._assert_ollama_ready(model)

        full = ([{"role": "system", "content": system}] if system else []) + messages
        try:
            resp = self._ollama.chat(
                model=model,
                messages=full,
                options={"temperature": temperature},
            )
        except Exception as exc:  # noqa: BLE001 - surface a clean hint
            raise LLMError(
                f"Ollama chat failed for model '{model}': {exc}. "
                f"Is the server running at {self.settings.ollama_host}?"
            ) from exc
        return resp["message"]["content"]

    def _assert_ollama_ready(self, model: str) -> None:
        """Fail fast with a fix hint if the server is down or model unpulled."""
        try:
            available = {m["model"] for m in self._ollama.list().get("models", [])}
        except Exception as exc:  # noqa: BLE001
            raise LLMError(
                f"Cannot reach Ollama at {self.settings.ollama_host}. "
                f"Start it (`ollama serve`) and retry. ({exc})"
            ) from exc
        # Ollama reports names with tags (e.g. 'qwen2.5:7b'); accept bare match too.
        if model not in available and f"{model}:latest" not in available:
            pretty = ", ".join(sorted(available)) or "(none)"
            raise LLMError(
                f"Ollama model '{model}' is not pulled. Run `ollama pull {model}`. "
                f"Available: {pretty}"
            )


def make_router(settings: Settings) -> LLMRouter:
    return LLMRouter(settings)
