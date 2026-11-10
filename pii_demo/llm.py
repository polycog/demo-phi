"""
Model setup. Any Pydantic AI model works; choose it with arguments or environment variables.

  PII_MODEL     model name, or a Pydantic AI model string such as
                "openai:gpt-5-mini" / "anthropic:claude-sonnet-5-5"   (default: openai/gpt-oss-20b)
  PII_BASE_URL  OpenAI-compatible endpoint (default: http://localhost:1234/v1, e.g. LM Studio).
                Set to "" to use the provider's own endpoint.
  PII_API_KEY   key for that endpoint (falls back to OPENAI_API_KEY, then a dummy for local servers)
"""

import os
from dataclasses import dataclass

from pydantic_ai.models import Model, infer_model

DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_BASE_URL = "http://localhost:1234/v1"


@dataclass(frozen=True)
class LLMConfig:
    model: str
    base_url: str | None
    timeout_secs: int = 180

    @classmethod
    def from_env(cls, model: str | None = None, base_url: str | None = None) -> "LLMConfig":
        model = model or os.environ.get("PII_MODEL", DEFAULT_MODEL)
        if base_url is None:
            base_url = os.environ.get("PII_BASE_URL", DEFAULT_BASE_URL)
        return cls(model=model, base_url=base_url or None)

    @property
    def label(self) -> str:
        return f"{self.model} @ {self.base_url}" if self.base_url else self.model


def api_key() -> str:
    """Key for an OpenAI-compatible endpoint; local servers accept any value"""
    return os.environ.get("PII_API_KEY") or os.environ.get("OPENAI_API_KEY") or "local"


def make_model(cfg: LLMConfig) -> Model:
    if cfg.base_url:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        name = cfg.model.removeprefix("openai:")
        return OpenAIChatModel(name, provider=OpenAIProvider(base_url=cfg.base_url, api_key=api_key()))
    return infer_model(cfg.model)
