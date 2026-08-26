from __future__ import annotations

import json
import os
import re
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, TypeVar

import yaml
from pydantic import BaseModel


StructuredT = TypeVar("StructuredT", bound=BaseModel)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


@dataclass(frozen=True)
class ModelProfile:
    id: str
    label: str
    provider: str
    model: str
    api_key: str
    base_url: str | None
    enabled: bool
    capabilities: tuple[str, ...]


def _message_text(message: Any) -> str:
    text = getattr(message, "text", None)
    if isinstance(text, str) and text:
        return text
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return str(content or "")


class ChatModelAdapter:
    def __init__(self, profile: ModelProfile):
        self.profile = profile
        self._model = None

    def _create_model(self):
        common = {
            "model": self.profile.model,
            "api_key": self.profile.api_key or "not-required",
            "timeout": float(os.getenv("LLM_REQUEST_TIMEOUT", "120")),
            "max_retries": 0,
        }
        if self.profile.provider in {"openai_compatible", "openai_responses"}:
            from langchain_openai import ChatOpenAI

            if self.profile.base_url:
                common["base_url"] = self.profile.base_url
            if self.profile.provider == "openai_responses":
                common["use_responses_api"] = True
            return ChatOpenAI(**common)
        if self.profile.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            common["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS", "4000"))
            return ChatAnthropic(**common)
        if self.profile.provider == "google_genai":
            from langchain_google_genai import ChatGoogleGenerativeAI

            common.pop("max_retries", None)
            return ChatGoogleGenerativeAI(**common)
        raise ValueError(f"Unsupported model provider: {self.profile.provider}")

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if status is not None:
            try:
                code = int(status)
                return code in {408, 429} or code >= 500
            except (TypeError, ValueError):
                pass
        name = type(exc).__name__.lower()
        text = str(exc).lower()
        return any(token in name or token in text for token in (
            "connection", "connecterror", "timeout", "tls", "temporarily unavailable",
            "server disconnected", "reset by peer", "502", "503", "504",
        ))

    async def _with_retry(self, operation):
        attempts = max(0, int(os.getenv("LLM_TRANSIENT_RETRIES", "2")))
        for attempt in range(attempts + 1):
            try:
                return await operation()
            except Exception as exc:
                if attempt >= attempts or not self._retryable(exc):
                    raise
                await asyncio.sleep(0.6 * (2 ** attempt))

    @property
    def model(self):
        if self._model is None:
            self._model = self._create_model()
        return self._model

    async def stream_text(self, messages: list[dict[str, str]]) -> AsyncGenerator[str, None]:
        emitted = False
        attempts = max(0, int(os.getenv("LLM_TRANSIENT_RETRIES", "2")))
        for attempt in range(attempts + 1):
            try:
                async for chunk in self.model.astream(messages):
                    text = _message_text(chunk)
                    if text:
                        emitted = True
                        yield text
                return
            except Exception as exc:
                if emitted or attempt >= attempts or not self._retryable(exc):
                    raise
                await asyncio.sleep(0.6 * (2 ** attempt))

    async def complete_text(self, messages: list[dict[str, str]]) -> str:
        response = await self._with_retry(lambda: self.model.ainvoke(messages))
        return _message_text(response).strip()

    async def complete_structured(
        self,
        messages: list[dict[str, str]],
        schema: type[StructuredT],
    ) -> StructuredT:
        if "structured_output" in self.profile.capabilities:
            try:
                result = await self._with_retry(
                    lambda: self.model.with_structured_output(schema).ainvoke(messages)
                )
                return result if isinstance(result, schema) else schema.model_validate(result)
            except Exception:
                # Some OpenAI-compatible gateways advertise features they do not actually implement.
                pass

        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        fallback_messages = [
            *messages,
            {
                "role": "user",
                "content": f"只返回符合以下 JSON Schema 的 JSON，不要使用 Markdown：{schema_json}",
            },
        ]
        last_error: Exception | None = None
        for _ in range(1):
            raw = await self.complete_text(fallback_messages)
            block = _JSON_BLOCK_RE.search(raw)
            candidate = block.group(1).strip() if block else raw.strip()
            try:
                return schema.model_validate(json.loads(candidate))
            except Exception as exc:
                last_error = exc
                fallback_messages.append({"role": "assistant", "content": raw})
        raise ValueError(f"Model did not return valid structured output: {last_error}")


class ModelRegistry:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or Path(__file__).resolve().parents[2] / "config" / "models.yaml"
        self._profiles: dict[str, ModelProfile] = {}
        self._adapters: dict[str, ChatModelAdapter] = {}

    def load(self) -> dict[str, ModelProfile]:
        data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        profiles = {}
        for config_id, raw in (data.get("profiles") or {}).items():
            enabled = bool(raw.get("enabled", False))
            enabled_env = raw.get("enabled_env")
            if enabled_env:
                enabled = bool(os.getenv(enabled_env))
            model = os.getenv(raw.get("model_env", "")) or raw.get("model_default", "")
            # The primary OpenAI-compatible profile is configured entirely by
            # LLM_* variables.  Expose and persist its concrete model name
            # instead of an opaque alias such as ``qwen-default``.
            profile_id = str(model) if raw.get("id_from_model", False) else str(config_id)
            label = str(model) if raw.get("label_from_model", False) else str(raw.get("label", profile_id))
            profiles[profile_id] = ModelProfile(
                id=profile_id,
                label=label,
                provider=str(raw.get("provider", "")),
                model=str(model),
                api_key=os.getenv(raw.get("api_key_env", ""), ""),
                base_url=os.getenv(raw.get("base_url_env", "")) if raw.get("base_url_env") else None,
                enabled=enabled,
                capabilities=tuple(raw.get("capabilities") or ()),
            )
        self._profiles = profiles
        return dict(profiles)

    def list(self) -> list[ModelProfile]:
        if not self._profiles:
            self.load()
        return list(self._profiles.values())

    def get_profile(self, profile_id: str | None = None) -> ModelProfile:
        if not self._profiles:
            self.load()
        active_model = os.getenv("LLM_MODEL_NAME", "").strip()
        resolved_id = profile_id or active_model
        # Existing SQLite runs may still contain the old internal aliases.
        # Keep retries readable without using those aliases for new runs.
        if resolved_id in {"qwen-default", "llm-default", "active-openai-compatible"}:
            resolved_id = active_model
        if not resolved_id:
            raise ValueError("LLM_MODEL_NAME is not configured")
        profile = self._profiles.get(resolved_id)
        if not profile:
            profile = next(
                (item for item in self._profiles.values() if item.model == resolved_id and item.enabled),
                None,
            )
        if not profile:
            raise ValueError(f"Unknown model or profile: {resolved_id}")
        if not profile.enabled:
            raise ValueError(f"Model profile is not configured: {resolved_id}")
        return profile

    def get_adapter(self, profile_id: str | None = None) -> ChatModelAdapter:
        profile = self.get_profile(profile_id)
        if profile.id not in self._adapters:
            self._adapters[profile.id] = ChatModelAdapter(profile)
        return self._adapters[profile.id]


_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
        _registry.load()
    return _registry
