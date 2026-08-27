import { describe, expect, it, vi, beforeEach } from "vitest";
import { api, ApiError } from "./client";

describe("api client", () => {
  beforeEach(() => {
    document.cookie = "tesqivo_csrf=csrf-abc";
    vi.restoreAllMocks();
  });

  it("attaches the CSRF token and web-client marker on mutations", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await api("/projects", { method: "POST", body: { key: "X" } });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-CSRF-Token"]).toBe("csrf-abc");
    expect(init.headers["X-Tesqivo-Client"]).toBe("web");
    expect(init.credentials).toBe("same-origin");
  });

  it("does not attach CSRF on GET", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api("/projects");
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["X-CSRF-Token"]).toBeUndefined();
  });

  it("throws ApiError carrying the PRS §13 envelope", async () => {
    const body = {
      error: {
        code: "VERSION_CONFLICT",
        message: "stale",
        status: 409,
        correlation_id: "abc",
        details: [],
        retryable: false,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async () => new Response(JSON.stringify(body), { status: 409 })),
    );
    let err: ApiError | undefined;
    try {
      await api("/x", { method: "POST", body: {} });
    } catch (e) {
      err = e as ApiError;
    }
    expect(err).toBeInstanceOf(ApiError);
    expect(err?.body).toMatchObject({ code: "VERSION_CONFLICT", retryable: false });
  });
});
