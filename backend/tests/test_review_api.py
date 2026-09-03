"""Code-review fixes: malformed identifiers return a structured 422, not a 500."""

import pytest


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/projects/not-a-uuid",
        "/api/v1/projects/not-a-uuid/members",
        "/api/v1/test-cases/12345",
        "/api/v1/projects/not-a-uuid/reports/summary",
        "/api/v1/notifications/nope/read",
    ],
)
@pytest.mark.asyncio
async def test_malformed_identifier_is_422_not_500(admin, path):
    method = admin.post if path.endswith("/read") else admin.get
    r = await method(path)
    assert r.status_code == 422, (path, r.status_code, r.text)
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert r.headers["X-Correlation-ID"]
