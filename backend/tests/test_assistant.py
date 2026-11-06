"""Ask TESQIVO help assistant: availability, streaming, grounding, authz, limits."""

import json

import pytest

from app.core.errors import AiProviderError


def _events(body: str) -> list[dict]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


async def _member(admin, project, make_user, username: str, role: str):
    user = await make_user(username)
    r = await admin.post(
        f"/api/v1/projects/{project['id']}/members", json={"user_id": user.user_id, "role": role}
    )
    assert r.status_code == 201, r.text
    return user


@pytest.mark.asyncio
async def test_status_reports_off_when_no_provider_configured(admin):
    r = await admin.get("/api/v1/assistant/status")
    assert r.status_code == 200
    assert r.json() == {"assistant": False, "generator": False}


@pytest.mark.asyncio
async def test_chat_without_provider_is_a_clean_503(admin):
    r = await admin.post("/api/v1/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "AI_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_chat_requires_sign_in(client, fake_ai):
    r = await client.post("/api/v1/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_chat_streams_answer_grounded_in_guide_and_role(admin, project, make_user, fake_ai):
    tester = await _member(admin, project, make_user, "tess", "tester")
    assert (await tester.get("/api/v1/assistant/status")).json()["assistant"] is True

    r = await tester.post(
        "/api/v1/assistant/chat",
        json={
            "messages": [{"role": "user", "content": "How do I approve a test case?"}],
            "project_id": project["id"],
            "page_path": "/p/DEMO/tests",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _events(r.text)
    assert [e["type"] for e in events] == ["delta", "delta", "done"]
    assert "".join(e["text"] for e in events if e["type"] == "delta").startswith("Open **Test Cases**")

    call = fake_ai.calls[0]
    stable, context = call["system"]
    assert "Submit for review" in stable                  # the user guide is in the cached prefix
    assert "Tester" in context and "DEMO" in context and "/p/DEMO/tests" in context
    assert "run tests in the Execution Runner" in context  # derived from the authz matrix
    assert "approve" not in context.split("Allowed in this project:")[1]  # testers can't approve
    assert call["effort"] == "low"


@pytest.mark.asyncio
async def test_stable_prefix_is_identical_across_users(admin, project, make_user, fake_ai):
    """Per-request context must stay out of the cached block or caching never hits."""
    viewer = await _member(admin, project, make_user, "vic", "viewer")
    body = {"messages": [{"role": "user", "content": "What is a cycle?"}], "project_id": project["id"]}
    await admin.post("/api/v1/assistant/chat", json=body)
    await viewer.post("/api/v1/assistant/chat", json=body)
    assert fake_ai.calls[0]["system"][0] == fake_ai.calls[1]["system"][0]
    assert fake_ai.calls[0]["system"][1] != fake_ai.calls[1]["system"][1]


@pytest.mark.asyncio
async def test_non_member_cannot_ask_about_a_project(project, make_user, fake_ai):
    outsider = await make_user("olly")
    r = await outsider.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "project_id": project["id"]},
    )
    assert r.status_code == 404  # existence not disclosed (D-010)
    assert fake_ai.calls == []


@pytest.mark.asyncio
async def test_history_is_trimmed_and_must_end_with_user(admin, fake_ai):
    r = await admin.post(
        "/api/v1/assistant/chat", json={"messages": [{"role": "assistant", "content": "hello"}]}
    )
    assert r.status_code == 422

    long_history = []
    for i in range(30):
        long_history += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]
    long_history.append({"role": "user", "content": "last"})
    r = await admin.post("/api/v1/assistant/chat", json={"messages": long_history})
    assert r.status_code == 200
    sent = fake_ai.calls[0]["messages"]
    assert len(sent) <= 20 and sent[0]["role"] == "user" and sent[-1]["content"] == "last"


@pytest.mark.asyncio
async def test_provider_failure_mid_stream_becomes_error_event(admin, fake_ai):
    fake_ai.error = AiProviderError("The AI service is busy. Try again in a minute.")
    r = await admin.post("/api/v1/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    events = _events(r.text)
    assert events[-1] == {"type": "error", "code": "AI_PROVIDER_ERROR", "message": "The AI service is busy. Try again in a minute."}


@pytest.mark.asyncio
async def test_per_user_hourly_limit(admin, fake_ai, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_requests_per_user_hour", 2)
    body = {"messages": [{"role": "user", "content": "hi"}]}
    assert (await admin.post("/api/v1/assistant/chat", json=body)).status_code == 200
    assert (await admin.post("/api/v1/assistant/chat", json=body)).status_code == 200
    r = await admin.post("/api/v1/assistant/chat", json=body)
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_kill_switch_overrides_a_configured_key(admin, monkeypatch):
    from app.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "ai_api_key", "sk-test")
    assert s.ai_available
    monkeypatch.setattr(s, "ai_enabled", False)
    assert not s.ai_available
    assert (await admin.get("/api/v1/assistant/status")).json()["assistant"] is False


def test_scoped_permissions_say_they_are_scoped():
    from app.core.context import Role
    from app.domain.ai.assistant import role_permissions

    tester = role_permissions(Role.tester)
    assert "edit test cases (only ones you created)" in tester
    assert "run tests in the Execution Runner (only ones assigned to you, or unassigned)" in tester
    assert "create test cases" not in tester
    manager = role_permissions(Role.test_manager)
    assert "edit test cases" in manager and "create test cases" in manager
    assert role_permissions(Role.viewer) == ["export to CSV", "view reports"]
