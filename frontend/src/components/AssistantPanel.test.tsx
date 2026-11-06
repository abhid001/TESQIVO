import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AssistantPanel, suggestionsFor } from "./AssistantPanel";
import { MiniMarkdown } from "./MiniMarkdown";
import { streamEvents } from "../api/client";

/** A fetch Response whose body arrives in the given (arbitrarily split) chunks. */
function sseResponse(chunks: string[], status = 200): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      chunks.forEach((ch) => c.enqueue(enc.encode(ch)));
      c.close();
    },
  });
  return new Response(body, { status, headers: { "content-type": "text/event-stream" } });
}

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe("streamEvents", () => {
  it("parses events split across network chunks", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      sseResponse(['data: {"type":"delta","te', 'xt":"Hel"}\n\ndata: {"type":"delta","text":"lo"}\n', '\ndata: {"type":"done"}\n\n']),
    );
    const seen: unknown[] = [];
    await streamEvents("/assistant/chat", { messages: [] }, (e) => seen.push(e));
    expect(seen).toEqual([
      { type: "delta", text: "Hel" },
      { type: "delta", text: "lo" },
      { type: "done" },
    ]);
  });

  it("throws the API error envelope when the request is refused", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "AI_NOT_CONFIGURED", message: "AI features are not configured on this instance.", status: 503, correlation_id: "x", details: [], retryable: false } }), { status: 503 }),
    );
    await expect(streamEvents("/assistant/chat", {}, () => {})).rejects.toThrow("AI features are not configured");
  });
});

describe("MiniMarkdown", () => {
  it("renders bold, code and lists, and never interprets HTML", () => {
    const { container } = render(
      <MiniMarkdown text={"Click **New test case**.\n\n1. Open `Test Cases`\n2. Save\n\n<img src=x onerror=alert(1)>"} />,
    );
    expect(container.querySelector("strong")?.textContent).toBe("New test case");
    expect(container.querySelector("code")?.textContent).toBe("Test Cases");
    expect(container.querySelectorAll("ol li")).toHaveLength(2);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
  });
});

describe("AssistantPanel", () => {
  it("offers page-specific starter questions", () => {
    expect(suggestionsFor("/p/DEMO/tests")[0]).toMatch(/approved/);
    expect(suggestionsFor("/p/DEMO/cycles")[0]).toMatch(/cycle/);
  });

  it("streams an answer and sends the page context", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      sseResponse(['data: {"type":"delta","text":"Use **Submit for review**"}\n\n', 'data: {"type":"done"}\n\n']),
    );
    render(
      <MemoryRouter initialEntries={["/p/DEMO/tests"]}>
        <AssistantPanel projectId="p-1" />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Ask TESQIVO" }));
    await userEvent.click(screen.getByRole("button", { name: "How do I get a test case approved?" }));

    expect(await screen.findByText("Submit for review")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/assistant\/chat$/);
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      messages: [{ role: "user", content: "How do I get a test case approved?" }],
      project_id: "p-1",
      page_path: "/p/DEMO/tests",
    });
  });

  it("shows a mid-stream error instead of hanging", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      sseResponse(['data: {"type":"error","code":"AI_PROVIDER_ERROR","message":"The AI service is busy."}\n\n']),
    );
    render(
      <MemoryRouter>
        <AssistantPanel />
      </MemoryRouter>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Ask TESQIVO" }));
    await userEvent.type(screen.getByPlaceholderText("Ask a question…"), "hello{Enter}");
    expect(await screen.findByText("The AI service is busy.")).toBeInTheDocument();
    expect(screen.queryByText("Thinking…")).toBeNull();
  });
});
