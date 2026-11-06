"""AI provider port (PRS §17: "the provider is behind an adapter").

Domain code depends on `AiProvider` only. `AnthropicProvider` is the one adapter
shipped today; tests install a fake with `set_provider_for_tests`. The provider
never touches the database - it turns prompts into text or validated JSON and
nothing else.

System prompts are passed as an ordered list of blocks: the first block is the
stable prefix (cached by the provider), later blocks carry per-request context.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.errors import AiDeclined, AiNotConfigured, AiProviderError

log = logging.getLogger("tesqivo.ai")

# Server-side refusal fallback: a declined request is re-run on Anthropic's
# recommended fallback model inside the same call instead of failing outright.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


@dataclass
class JsonResult:
    data: dict[str, Any]
    model: str
    usage: Usage = field(default_factory=Usage)


class AiProvider(Protocol):
    name: str
    model: str

    def stream_text(
        self, *, system: list[str], messages: list[dict[str, str]], effort: str, max_tokens: int
    ) -> AsyncIterator[str]: ...

    async def generate_json(
        self, *, system: list[str], prompt: str, schema: dict[str, Any], effort: str, max_tokens: int
    ) -> JsonResult: ...


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, *, api_key: str, model: str, http_client: Any = None) -> None:
        from anthropic import AsyncAnthropic

        self.model = model
        self._client = AsyncAnthropic(
            api_key=api_key, timeout=300.0, max_retries=2, http_client=http_client
        )

    @staticmethod
    def _system(blocks: list[str]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, text in enumerate(blocks):
            block: dict[str, Any] = {"type": "text", "text": text}
            if i == 0:
                block["cache_control"] = {"type": "ephemeral"}
            out.append(block)
        return out

    async def stream_text(
        self, *, system: list[str], messages: list[dict[str, str]], effort: str, max_tokens: int
    ) -> AsyncIterator[str]:
        import anthropic

        try:
            async with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=self._system(system),
                messages=messages,  # type: ignore[arg-type]
                output_config={"effort": effort},  # type: ignore[typeddict-item]
                betas=[_FALLBACK_BETA],
                fallbacks="default",  # type: ignore[arg-type]
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIStatusError as exc:
            raise _map_status_error(exc)
        except anthropic.APIConnectionError:
            raise AiProviderError("The AI service could not be reached. Try again shortly.")
        if final.stop_reason == "refusal":
            raise AiDeclined("The assistant can't help with that request.")

    async def generate_json(
        self, *, system: list[str], prompt: str, schema: dict[str, Any], effort: str, max_tokens: int
    ) -> JsonResult:
        import anthropic

        try:
            # Streamed so long, high-effort generations never hit an HTTP timeout.
            async with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=self._system(system),
                messages=[{"role": "user", "content": prompt}],
                output_config={  # type: ignore[typeddict-item]
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
                betas=[_FALLBACK_BETA],
                fallbacks="default",  # type: ignore[arg-type]
            ) as stream:
                final = await stream.get_final_message()
        except anthropic.APIStatusError as exc:
            raise _map_status_error(exc)
        except anthropic.APIConnectionError:
            raise AiProviderError("The AI service could not be reached. Try again shortly.")

        if final.stop_reason == "refusal":
            raise AiDeclined("The AI model declined to generate suggestions for this input.")
        if final.stop_reason == "max_tokens":
            raise AiDeclined("The AI output was cut off. Ask for fewer test cases and try again.")
        text = next((b.text for b in final.content if b.type == "text"), "")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise AiDeclined("The AI returned output that could not be read. Try again.")
        u = final.usage
        return JsonResult(
            data=data,
            model=final.model,
            usage=Usage(
                input_tokens=u.input_tokens or 0,
                output_tokens=u.output_tokens or 0,
                cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            ),
        )


def _map_status_error(exc: Exception) -> Exception:
    import anthropic

    log.warning("AI provider error: %s", type(exc).__name__)
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return AiNotConfigured("The AI provider rejected the configured API key. Contact your administrator.")
    if isinstance(exc, anthropic.RateLimitError):
        return AiProviderError("The AI service is busy. Try again in a minute.")
    if isinstance(exc, anthropic.BadRequestError):
        return AiDeclined("The AI service rejected this request.")
    return AiProviderError("The AI service had a problem. Try again shortly.")


_override: AiProvider | None = None
_cached: AiProvider | None = None


def get_provider() -> AiProvider:
    """The configured provider, or AiNotConfigured when AI is off on this instance."""
    global _cached
    if _override is not None:
        return _override
    settings = get_settings()
    if not settings.ai_available:
        raise AiNotConfigured("AI features are not configured on this instance.")
    if _cached is None:
        _cached = AnthropicProvider(api_key=settings.ai_api_key.strip(), model=settings.ai_model)
    return _cached


def ai_available() -> bool:
    return _override is not None or get_settings().ai_available


def set_provider_for_tests(provider: AiProvider | None) -> None:
    global _override, _cached
    _override = provider
    _cached = None
