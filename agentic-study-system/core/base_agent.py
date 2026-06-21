"""BaseAgent — common machinery for every agent in the system.

Each agent is a thin object that knows (a) which engine/model it routes to and
(b) which system prompt it loads. The important shared behaviour lives in
`run_validated`: the bounded re-prompt loop that turns a non-deterministic model
into a deterministic rule-follower.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from core.config import Settings
from core.llm_router import LLMRouter, Message
from core.validators import Validator, run_validators

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class BaseAgent:
    def __init__(
        self,
        name: str,
        settings: Settings,
        router: LLMRouter,
        system_prompt_file: str | None = None,
    ):
        self.name = name
        self.settings = settings
        self.router = router
        self.route = settings.route(name)
        self.system_prompt = (
            self._load_prompt(system_prompt_file) if system_prompt_file else ""
        )

    def _load_prompt(self, filename: str) -> str:
        path = PROMPTS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"System prompt not found: {path}")
        return path.read_text(encoding="utf-8")

    @property
    def engine(self) -> str:
        return self.route.engine

    @property
    def model(self) -> str:
        return self.route.model

    def run(
        self,
        messages: Sequence[Message],
        *,
        system: str | None = None,
        max_tokens: int = 4096,
    ) -> str:
        """Single, unvalidated call routed by this agent's config entry."""
        return self.router.chat(
            messages,
            engine=self.engine,
            model=self.model,
            system=system if system is not None else self.system_prompt,
            temperature=self.route.temperature,
            max_tokens=max_tokens,
        )

    def run_validated(
        self,
        messages: Sequence[Message],
        validators: Sequence[Validator],
        *,
        system: str | None = None,
        max_tokens: int = 4096,
        max_retries: int | None = None,
    ) -> str:
        """Call the model, then enforce pedagogical rules deterministically.

        On a validator failure the concrete fix instructions are appended to the
        conversation and the model is re-prompted, up to `max_retries` times.
        The best (last) attempt is returned even if it still fails, so the
        caller can decide whether to surface a warning.
        """
        retries = self.settings.max_retries if max_retries is None else max_retries
        convo: list[Message] = list(messages)
        last = ""
        for attempt in range(retries + 1):
            last = self.run(convo, system=system, max_tokens=max_tokens)
            result = run_validators(last, validators)
            if result.ok:
                return last
            if attempt == retries:
                break
            feedback = (
                "Your previous response violated these required rules:\n- "
                + "\n- ".join(result.failures)
                + "\n\nRewrite the FULL response so every rule is satisfied. "
                "Keep all correct content; fix only what the rules demand."
            )
            convo = convo + [
                {"role": "assistant", "content": last},
                {"role": "user", "content": feedback},
            ]
        return last  # exhausted retries; return best effort
