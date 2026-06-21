"""Configuration loader for the Agentic Study System.

Merges `.env` (secrets/endpoints) with `config.yaml` (the routing table) and
resolves each agent's logical engine ("api"/"ollama") into a concrete
provider + model. Keeping this resolution in one place is what makes the
hybrid router deterministic: every agent reads the same table.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # python-dotenv optional at import time
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

# Project root = parent of this file's directory (core/ -> project root).
ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"

# Logical engine names used in config.yaml.
ENGINE_API = "api"
ENGINE_OLLAMA = "ollama"

# Concrete providers the logical "api" engine can resolve to (via API_PROVIDER).
# "vllm" is a self-hosted, OpenAI-compatible server (e.g. gpt-oss on tailab).
API_PROVIDERS = ("anthropic", "openai", "vllm")


@dataclass(frozen=True)
class AgentRoute:
    """Fully-resolved routing for a single agent."""

    name: str
    engine: str            # "anthropic" | "openai" | "ollama"  (concrete)
    model: str
    temperature: float
    extras: dict           # any extra per-agent keys from config.yaml (e.g. max_images)


@dataclass(frozen=True)
class Settings:
    """Top-level runtime settings + the resolved agent routing table."""

    api_provider: str                  # "anthropic" | "openai" | "vllm"
    anthropic_api_key: str | None
    openai_api_key: str | None
    openai_base_url: str | None        # optional OpenAI-compatible endpoint
    vllm_base_url: str                 # OpenAI-compatible endpoint (e.g. tailab tunnel)
    vllm_api_key: str | None           # usually a dummy token; vLLM ignores it unless --api-key set
    lightrag_base_url: str | None
    lightrag_api_key: str | None
    lightrag_default_mode: str
    ollama_host: str
    max_retries: int
    _routes: dict[str, AgentRoute]
    root: Path

    def route(self, agent_name: str) -> AgentRoute:
        try:
            return self._routes[agent_name]
        except KeyError as exc:
            known = ", ".join(sorted(self._routes)) or "(none)"
            raise KeyError(
                f"No routing entry for agent '{agent_name}' in config.yaml. "
                f"Known agents: {known}"
            ) from exc


def load_settings(config_path: Path | None = None) -> Settings:
    """Load `.env` + `config.yaml` and resolve the routing table once."""
    load_dotenv(ROOT / ".env")

    path = config_path or CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    api_provider = os.getenv("API_PROVIDER", "anthropic").strip().lower()
    if api_provider not in API_PROVIDERS:
        raise ValueError(
            f"API_PROVIDER must be one of {API_PROVIDERS}, got '{api_provider}'"
        )

    api_models: dict[str, str] = raw.get("api_models", {})

    _reserved = {"engine", "model", "temperature"}
    routes: dict[str, AgentRoute] = {}
    for name, spec in (raw.get("agents") or {}).items():
        engine = str(spec.get("engine", ENGINE_API)).lower()
        model = str(spec.get("model", "auto"))
        temperature = float(spec.get("temperature", 0.4))
        extras = {k: v for k, v in spec.items() if k not in _reserved}

        if engine == ENGINE_API:
            concrete_engine = api_provider
            if model == "auto":
                model = api_models.get(api_provider, "")
                if not model:
                    raise ValueError(
                        f"Agent '{name}' uses model 'auto' but no default model "
                        f"is set for provider '{api_provider}' in config.yaml:api_models"
                    )
        elif engine == ENGINE_OLLAMA:
            concrete_engine = ENGINE_OLLAMA
            if model == "auto":
                raise ValueError(
                    f"Agent '{name}' on ollama must name an explicit model "
                    f"(e.g. qwen2.5:7b), not 'auto'."
                )
        else:
            raise ValueError(
                f"Agent '{name}' has unknown engine '{engine}'. "
                f"Use '{ENGINE_API}' or '{ENGINE_OLLAMA}'."
            )

        routes[name] = AgentRoute(
            name=name, engine=concrete_engine, model=model,
            temperature=temperature, extras=extras,
        )

    return Settings(
        api_provider=api_provider,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
        vllm_base_url=os.getenv("VLLM_BASE_URL", "http://localhost:8006/v1"),
        vllm_api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
        lightrag_base_url=os.getenv("LIGHTRAG_BASE_URL"),
        lightrag_api_key=os.getenv("LIGHTRAG_API_KEY"),
        lightrag_default_mode=os.getenv("LIGHTRAG_DEFAULT_MODE", "mix"),
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        max_retries=int((raw.get("validation") or {}).get("max_retries", 2)),
        _routes=routes,
        root=ROOT,
    )
