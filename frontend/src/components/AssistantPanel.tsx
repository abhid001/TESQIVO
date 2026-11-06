import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { ApiError, streamEvents } from "../api/client";
import { errText } from "../ui";
import { Icons } from "./icons";
import { MiniMarkdown } from "./MiniMarkdown";

type Msg = { role: "user" | "assistant"; content: string; error?: boolean };
type ChatEvent =
  | { type: "delta"; text: string }
  | { type: "done" }
  | { type: "error"; code: string; message: string };

const STORE_KEY = "tq.assistant.chat";

/** Starter questions for the section the user is looking at. */
export function suggestionsFor(path: string): string[] {
  if (path.includes("/tests")) return ["How do I get a test case approved?", "Why did editing a test case create a new version?"];
  if (path.includes("/requirements")) return ["How do I link tests to a requirement?", "When does a requirement count as covered?"];
  if (path.includes("/cycles")) return ["How do I run a test cycle?", "What happens when I activate a cycle?"];
  if (path.includes("/plans")) return ["What's the difference between a plan and a cycle?", "How do I add tests to a plan?"];
  if (path.includes("/dashboard")) return ["What does Requirements Coverage measure?", "How is the pass rate calculated?"];
  return ["What can I do with my role?", "How do I get started with TESQIVO?"];
}

function load(): Msg[] {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    return raw ? (JSON.parse(raw) as Msg[]) : [];
  } catch {
    return [];
  }
}

function save(msgs: Msg[]) {
  try { sessionStorage.setItem(STORE_KEY, JSON.stringify(msgs.slice(-40))); } catch { /* ignore */ }
}

/** "Ask TESQIVO": floating help chat. Rendered only when the server reports the
 *  assistant is configured (GET /assistant/status). */
export function AssistantPanel({ projectId }: { projectId?: string }) {
  const loc = useLocation();
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>(load);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => save(msgs), [msgs]);
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs, open]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open]);

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    const history = [...msgs.filter((m) => !m.error), { role: "user" as const, content: q }];
    setMsgs([...history, { role: "assistant", content: "" }]);
    setInput("");
    setBusy(true);
    const ctrl = new AbortController();
    abort.current = ctrl;
    // No-op once the chat was cleared mid-stream ("New chat").
    const setLast = (fn: (m: Msg) => Msg) =>
      setMsgs((cur) => (cur.length ? [...cur.slice(0, -1), fn(cur[cur.length - 1])] : cur));
    try {
      await streamEvents<ChatEvent>(
        "/assistant/chat",
        {
          messages: history.map(({ role, content }) => ({ role, content })),
          project_id: projectId ?? null,
          page_path: loc.pathname,
        },
        (ev) => {
          if (ev.type === "delta") setLast((m) => ({ ...m, content: m.content + ev.text }));
          if (ev.type === "error") setLast((m) => ({ ...m, content: m.content ? `${m.content}\n\n${ev.message}` : ev.message, error: true }));
        },
        ctrl.signal,
      );
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        setLast((m) => (m.content ? m : { ...m, content: "Stopped.", error: true }));
      } else {
        setLast((m) => ({ ...m, content: e instanceof ApiError ? e.body.message : errText(e), error: true }));
      }
    } finally {
      setBusy(false);
      abort.current = null;
    }
  };

  const reset = () => { abort.current?.abort(); setMsgs([]); };

  if (!open) {
    return (
      <button className="assistant-fab" onClick={() => setOpen(true)} aria-label="Ask TESQIVO">
        {Icons.sparkle} Ask TESQIVO
      </button>
    );
  }

  return (
    <section className="assistant-panel" role="dialog" aria-label="Ask TESQIVO">
      <header className="assistant-head">
        <span className="assistant-title">{Icons.sparkle} Ask TESQIVO</span>
        <span className="spacer-flex" />
        {msgs.length > 0 && <button className="ghost sm" onClick={reset}>New chat</button>}
        <button className="icon-btn" onClick={() => setOpen(false)} aria-label="Close assistant">✕</button>
      </header>

      <div className="assistant-body" ref={listRef} aria-live="polite">
        {msgs.length === 0 ? (
          <div className="assistant-empty">
            <p>Ask how TESQIVO works: workflows, screens, roles, terms.</p>
            {suggestionsFor(loc.pathname).map((s) => (
              <button key={s} className="assistant-chip" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        ) : (
          msgs.map((m, i) => (
            <div key={i} className={`assistant-msg ${m.role}${m.error ? " error" : ""}`}>
              {m.role === "assistant"
                ? (m.content ? <MiniMarkdown text={m.content} /> : <span className="assistant-typing">Thinking…</span>)
                : m.content}
            </div>
          ))
        )}
      </div>

      <form className="assistant-input" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <textarea
          ref={inputRef}
          rows={2}
          value={input}
          maxLength={4000}
          placeholder="Ask a question…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
          }}
        />
        {busy
          ? <button type="button" onClick={() => abort.current?.abort()}>Stop</button>
          : <button type="submit" className="primary" disabled={!input.trim()}>Send</button>}
      </form>
      <p className="assistant-note">AI answers can be wrong. It can't see or change your project data.</p>
    </section>
  );
}
