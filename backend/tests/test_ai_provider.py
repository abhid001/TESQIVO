"""AnthropicProvider against a mocked HTTP transport: the exact request we send and
how we read streamed responses, refusals, truncation and HTTP errors."""

import json

import httpx2
import pytest
from anthropic import DefaultAsyncHttpxClient

from app.core.errors import AiDeclined, AiNotConfigured, AiProviderError
from app.domain.ai.provider import AnthropicProvider


def _sse(events: list[tuple[str, dict]]) -> bytes:
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events).encode()


def _stream_body(text: str, *, stop_reason: str = "end_turn") -> bytes:
    return _sse([
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 50, "output_tokens": 1, "cache_read_input_tokens": 40}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "text", "text": ""}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "text_delta", "text": text[: len(text) // 2]}}),
        ("content_block_delta", {"type": "content_block_delta", "index": 0,
                                 "delta": {"type": "text_delta", "text": text[len(text) // 2:]}}),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                           "usage": {"output_tokens": 30}}),
        ("message_stop", {"type": "message_stop"}),
    ])


def _provider(handler) -> tuple[AnthropicProvider, list[httpx2.Request]]:
    seen: list[httpx2.Request] = []

    def _wrapped(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return handler(request)

    client = DefaultAsyncHttpxClient(transport=httpx2.MockTransport(_wrapped))
    p = AnthropicProvider(api_key="sk-test", model="claude-opus-5-5", http_client=client)
    p._client = p._client.with_options(max_retries=0)
    return p, seen


def _ok(body: bytes) -> httpx2.Response:
    return httpx2.Response(200, content=body, headers={"content-type": "text/event-stream"})


@pytest.mark.asyncio
async def test_stream_text_request_shape_and_output():
    p, seen = _provider(lambda r: _ok(_stream_body("Click New test case.")))
    out = [t async for t in p.stream_text(
        system=["STABLE", "CTX"], messages=[{"role": "user", "content": "hi"}], effort="low", max_tokens=100)]
    assert "".join(out) == "Click New test case."

    req = seen[0]
    body = json.loads(req.content)
    assert req.url.path == "/v1/messages"
    assert "server-side-fallback-2026-07-01" in req.headers["anthropic-beta"]
    assert body["fallbacks"] == "default"
    assert body["model"] == "claude-opus-5-5" and body["stream"] is True
    assert body["output_config"] == {"effort": "low"}
    assert body["system"][0] == {"type": "text", "text": "STABLE", "cache_control": {"type": "ephemeral"}}
    assert body["system"][1] == {"type": "text", "text": "CTX"}  # volatile block stays uncached
    assert "thinking" not in body and "temperature" not in body


@pytest.mark.asyncio
async def test_generate_json_parses_and_reports_usage():
    payload = {"assumptions": [], "open_questions": [], "test_cases": []}
    p, seen = _provider(lambda r: _ok(_stream_body(json.dumps(payload))))
    res = await p.generate_json(system=["S"], prompt="P", schema={"type": "object"}, effort="high", max_tokens=64000)
    assert res.data == payload and res.model == "claude-opus-5-5"
    assert res.usage.output_tokens == 30 and res.usage.cache_read_tokens == 40
    body = json.loads(seen[0].content)
    assert body["output_config"] == {"effort": "high", "format": {"type": "json_schema", "schema": {"type": "object"}}}
    assert body["messages"] == [{"role": "user", "content": "P"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
async def test_generate_json_unusable_stop_reasons(stop_reason):
    p, _ = _provider(lambda r: _ok(_stream_body("{}", stop_reason=stop_reason)))
    with pytest.raises(AiDeclined):
        await p.generate_json(system=["S"], prompt="P", schema={}, effort="high", max_tokens=10)


@pytest.mark.asyncio
async def test_stream_refusal_raises_after_text():
    p, _ = _provider(lambda r: _ok(_stream_body("partial", stop_reason="refusal")))
    with pytest.raises(AiDeclined):
        [t async for t in p.stream_text(system=["S"], messages=[{"role": "user", "content": "x"}],
                                         effort="low", max_tokens=10)]


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "error"), [
    (401, AiNotConfigured), (429, AiProviderError), (400, AiDeclined), (529, AiProviderError),
])
async def test_http_errors_map_to_domain_errors(status, error):
    def handler(r):
        return httpx2.Response(status, json={"type": "error", "error": {"type": "x", "message": "nope"}})

    p, _ = _provider(handler)
    with pytest.raises(error):
        await p.generate_json(system=["S"], prompt="P", schema={}, effort="high", max_tokens=10)
