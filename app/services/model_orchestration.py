from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.db.models import ModelAuditLog
from app.intelligence.prompt_builder import build_classification_prompt


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"


@dataclass
class ModelResult:
    text: str
    provider: str
    model: str
    confidence_score: float | None = None
    metadata: dict[str, Any] | None = None


class LLMProvider(Protocol):
    provider_name: str

    def generate_reply(self, prompt: str, *, model: str = DEFAULT_GEMINI_MODEL, max_output_tokens: int = 700, temperature: float = 0.25) -> ModelResult:
        ...

    async def generate_reply_async(self, prompt: str, *, model: str = DEFAULT_GEMINI_MODEL, max_output_tokens: int = 700, temperature: float = 0.25) -> ModelResult:
        ...

    async def classify_message(self, message: str, client_config: dict[str, Any] | None = None) -> dict[str, Any]:
        ...


class GeminiProvider:
    provider_name = "gemini"

    def __init__(self, api_key: str | None = None):
        self.api_key = (api_key if api_key is not None else get_settings().gemini_api_key).strip()

    def _url(self, model: str) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def _extract_text(self, payload: dict[str, Any]) -> str:
        return (
            payload.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

    def generate_reply(self, prompt: str, *, model: str = DEFAULT_GEMINI_MODEL, max_output_tokens: int = 700, temperature: float = 0.25) -> ModelResult:
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured")
        response = httpx.post(
            self._url(model),
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens},
            },
            timeout=20.0,
        )
        response.raise_for_status()
        return ModelResult(text=self._extract_text(response.json()), provider=self.provider_name, model=model)

    async def generate_reply_async(self, prompt: str, *, model: str = DEFAULT_GEMINI_MODEL, max_output_tokens: int = 700, temperature: float = 0.25) -> ModelResult:
        if not self.api_key:
            raise RuntimeError("Gemini API key is not configured")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                self._url(model),
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens},
                },
            )
            response.raise_for_status()
            return ModelResult(text=self._extract_text(response.json()), provider=self.provider_name, model=model)

    async def classify_message(self, message: str, client_config: dict[str, Any] | None = None) -> dict[str, Any]:
        result = await self.generate_reply_async(
            build_classification_prompt(message, client_config),
            model=DEFAULT_GEMINI_MODEL,
            max_output_tokens=700,
            temperature=0,
        )
        return {"raw_text": result.text, "provider": result.provider, "model": result.model}


class ModelOrchestrator:
    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider or GeminiProvider()

    def generate_reply(self, prompt: str, **kwargs) -> ModelResult:
        return self.provider.generate_reply(prompt, **kwargs)

    async def generate_reply_async(self, prompt: str, **kwargs) -> ModelResult:
        return await self.provider.generate_reply_async(prompt, **kwargs)

    async def classify_message(self, message: str, client_config: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.provider.classify_message(message, client_config)

    def summarize(self, text: str, max_chars: int = 400) -> str:
        words = (text or "").split()
        if len(text or "") <= max_chars:
            return (text or "").strip()
        return " ".join(words)[:max_chars].strip()

    def explain_risk(self, risk: dict[str, Any]) -> str:
        explanation = risk.get("explanation") or []
        if explanation:
            return "Risk increased due to: " + ", ".join(str(item) for item in explanation[:5])
        return f"Risk level is {risk.get('level', 'unknown')} with score {risk.get('score', 0)}."


def get_model_orchestrator() -> ModelOrchestrator:
    return ModelOrchestrator()


def audit_model_call(
    db,
    *,
    client_id=None,
    complaint_id=None,
    customer_id=None,
    provider: str,
    model: str | None,
    task_type: str,
    prompt: str,
    output: str = "",
    confidence_score: float | None = None,
    latency_ms: int | None = None,
    status: str = "succeeded",
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
):
    if db is None:
        return None
    prompt_text = prompt or ""
    entry = ModelAuditLog(
        client_id=client_id,
        complaint_id=complaint_id,
        customer_id=customer_id,
        provider=provider,
        model=model,
        task_type=task_type,
        prompt_hash=hashlib.sha256(prompt_text.encode("utf-8")).hexdigest() if prompt_text else None,
        prompt_preview=prompt_text[:1000],
        output_preview=(output or "")[:1000],
        confidence_score=confidence_score,
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.flush()
    return entry


def parse_json_model_output(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def timed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)
