// PROPRIETARY - see ./LICENSE.
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import { useRole } from "../auth/AuthContext";
import { StepEditor, type DraftStep } from "../components/StepEditor";
import { Badge, Card, Dialog, EmptyState, Field, cap, errText, useToast } from "../ui";
import type { Generation, Suggestion, SuggestionPayload } from "./types";

const TEST_TYPES = ["functional", "negative", "boundary", "security", "accessibility", "usability", "performance", "integration"];
const PRIORITIES = ["critical", "high", "medium", "low"];

/** Accepting creates a test case, which is a Test Manager action (D-018). */
function canAccept(role: string | null) {
  return role === "test_manager" || role === "system_admin";
}

export function GenerationReviewPage() {
  const { projectKey, generationId } = useParams();
  const { project } = useProject(projectKey);
  const role = useRole(project?.id);
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<Suggestion | null>(null);
  const [rejecting, setRejecting] = useState<Suggestion | null>(null);

  const key = ["ai-generation", generationId];
  const gen = useQuery({
    queryKey: key,
    queryFn: () => http.get<Generation>(`/ee/ai/generations/${generationId}`),
    refetchInterval: (q) => (q.state.data && ["queued", "running"].includes(q.state.data.status) ? 2000 : false),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: key });

  const accept = useMutation({
    mutationFn: (s: Suggestion) => http.post<Suggestion>(`/ee/ai/suggestions/${s.id}/accept`, {}),
    onSuccess: (s) => { toast(`Created ${s.test_case_key} as a Draft`); refresh(); },
    onError: (e) => toast(errText(e), "error"),
  });

  if (gen.isLoading || !project) return <p>Loading…</p>;
  if (gen.isError || !gen.data) return <EmptyState>{errText(gen.error)}</EmptyState>;
  const g = gen.data;
  const suggestions = g.suggestions ?? [];
  const pending = suggestions.filter((s) => s.status === "pending");
  const running = g.status === "queued" || g.status === "running";

  const acceptAll = async () => {
    for (const s of pending) {
      try { await accept.mutateAsync(s); } catch { break; }
    }
  };

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h2>AI suggestions</h2>
          <p className="muted" style={{ margin: 0 }}>
            <Link to={`/p/${projectKey}/ai`}>All generations</Link>
            {g.model && <> · {g.model}</>}
            {g.output_tokens > 0 && <> · {(g.input_tokens + g.output_tokens).toLocaleString()} tokens</>}
          </p>
        </div>
        <span className="spacer-flex" />
        <Badge value={g.status} />
        {canAccept(role) && pending.length > 1 && (
          <button className="primary" disabled={accept.isPending} onClick={acceptAll}>
            Accept all {pending.length}
          </button>
        )}
      </div>

      <Card>
        <span className="field-label">Sources</span>
        <div className="inline-actions" style={{ flexWrap: "wrap", marginTop: 6 }}>
          {g.sources.map((s) => (
            <button key={s.id} className="pill" onClick={() => nav(
              s.type === "requirement"
                ? `/p/${projectKey}/requirements?req=${encodeURIComponent(s.key)}`
                : `/p/${projectKey}/scenarios`)}>
              {s.key} · {s.title}
            </button>
          ))}
          {g.story_text && <span className="pill">User story</span>}
        </div>
      </Card>

      {running && (
        <p className="notice info">Generating test cases… This page updates on its own; you can leave and come back.</p>
      )}
      {g.status === "failed" && <p className="notice err">{g.error_summary ?? "Generation failed."}</p>}
      {g.status === "completed" && g.error_summary && <p className="notice">{g.error_summary}</p>}

      {(g.open_questions.length > 0 || g.assumptions.length > 0) && (
        <Card>
          {g.open_questions.length > 0 && (
            <>
              <span className="field-label">Questions to settle with the requirement owner</span>
              <ul>{g.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
            </>
          )}
          {g.assumptions.length > 0 && (
            <>
              <span className="field-label">Assumptions the AI made</span>
              <ul>{g.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </>
          )}
        </Card>
      )}

      {!canAccept(role) && pending.length > 0 && (
        <p className="notice">You can edit or reject suggestions. A test manager accepts them into Test Cases.</p>
      )}

      {suggestions.map((s) => (
        <SuggestionCard
          key={s.id}
          s={s}
          projectKey={projectKey!}
          canAccept={canAccept(role)}
          busy={accept.isPending}
          onAccept={() => accept.mutate(s)}
          onEdit={() => setEditing(s)}
          onReject={() => setRejecting(s)}
        />
      ))}

      {editing && <EditDialog s={editing} sources={g.sources.filter((x) => x.type === "requirement").map((x) => x.key)}
        onClose={() => setEditing(null)} onDone={() => { setEditing(null); refresh(); }} />}
      {rejecting && <RejectDialog s={rejecting} onClose={() => setRejecting(null)} onDone={() => { setRejecting(null); refresh(); }} />}
    </div>
  );
}

function SuggestionCard({ s, projectKey, canAccept, busy, onAccept, onEdit, onReject }: {
  s: Suggestion; projectKey: string; canAccept: boolean; busy: boolean;
  onAccept: () => void; onEdit: () => void; onReject: () => void;
}) {
  const p = s.payload;
  return (
    <Card className={`ai-suggestion ${s.status !== "pending" ? "decided" : ""}`}>
      <div className="ai-suggestion-head">
        <h3>{p.title}</h3>
        <Badge value={p.priority} />
        <span className="pill">{cap(p.test_type)}</span>
        {p.automation_candidate && <span className="pill">Automation candidate</span>}
        {s.edited && <span className="pill">Edited</span>}
        {s.status !== "pending" && <Badge value={s.status} />}
      </div>
      {s.possible_duplicate_of && (
        <p className="notice" style={{ margin: 0 }}>
          Looks like existing test{" "}
          <Link to={`/p/${projectKey}/tests?q=${encodeURIComponent(s.possible_duplicate_of)}`}>{s.possible_duplicate_of}</Link>.
          Check before accepting.
        </p>
      )}
      {p.objective && <p style={{ margin: 0 }}>{p.objective}</p>}
      {p.preconditions && <p style={{ margin: 0 }}><span className="muted">Preconditions:</span> {p.preconditions}</p>}
      <div className="table-wrap">
        <table className="ai-steps">
          <thead><tr><th>#</th><th>Action</th><th>Expected result</th></tr></thead>
          <tbody>
            {p.steps.map((st, i) => (
              <tr key={i}><td>{i + 1}</td><td>{st.action}</td><td>{st.expected_result}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {(p.rationale || p.requirement_keys.length > 0) && (
        <p className="muted" style={{ margin: 0, fontSize: 12.5 }}>
          {p.requirement_keys.length > 0 && <>Covers {p.requirement_keys.join(", ")}. </>}
          {p.rationale}
        </p>
      )}
      {s.status === "pending" ? (
        <div className="inline-actions">
          {canAccept && <button className="primary" disabled={busy} onClick={onAccept}>Accept as Draft</button>}
          <button onClick={onEdit}>Edit</button>
          <button className="ghost" onClick={onReject}>Reject</button>
        </div>
      ) : s.status === "accepted" && s.test_case_id ? (
        <p style={{ margin: 0 }}>
          Added as <Link to={`/p/${projectKey}/tests/${s.test_case_id}`}>{s.test_case_key}</Link> (Draft, needs review).
        </p>
      ) : s.reject_reason ? (
        <p className="muted" style={{ margin: 0 }}>Rejected: {s.reject_reason}</p>
      ) : null}
    </Card>
  );
}

function EditDialog({ s, sources, onClose, onDone }: {
  s: Suggestion; sources: string[]; onClose: () => void; onDone: () => void;
}) {
  const toast = useToast();
  const [p, setP] = useState<SuggestionPayload>(s.payload);
  const [steps, setSteps] = useState<DraftStep[]>(s.payload.steps.map((st) => ({ ...st, is_required: true })));
  const set = (patch: Partial<SuggestionPayload>) => setP({ ...p, ...patch });

  const save = useMutation({
    mutationFn: () => http.patch(`/ee/ai/suggestions/${s.id}`, {
      expected_version: s.version,
      payload: { ...p, steps: steps.map(({ action, expected_result }) => ({ action, expected_result })) },
    }),
    onSuccess: () => { toast("Suggestion updated"); onDone(); },
    onError: (e) => toast(errText(e), "error"),
  });

  return (
    <Dialog title="Edit suggestion" onClose={onClose}>
      <Field label="Title"><input value={p.title} maxLength={300} onChange={(e) => set({ title: e.target.value })} /></Field>
      <Field label="Objective (becomes the description)">
        <textarea rows={2} value={p.objective} onChange={(e) => set({ objective: e.target.value })} />
      </Field>
      <Field label="Preconditions">
        <textarea rows={2} value={p.preconditions} onChange={(e) => set({ preconditions: e.target.value })} />
      </Field>
      <StepEditor steps={steps} onChange={setSteps} />
      <div className="inline-actions" style={{ marginTop: 12 }}>
        <Field label="Type">
          <select value={p.test_type} onChange={(e) => set({ test_type: e.target.value })}>
            {TEST_TYPES.map((t) => <option key={t} value={t}>{cap(t)}</option>)}
          </select>
        </Field>
        <Field label="Priority">
          <select value={p.priority} onChange={(e) => set({ priority: e.target.value })}>
            {PRIORITIES.map((t) => <option key={t} value={t}>{cap(t)}</option>)}
          </select>
        </Field>
      </div>
      <label style={{ display: "flex", gap: 8, margin: "4px 0 12px" }}>
        <input type="checkbox" checked={p.automation_candidate} onChange={(e) => set({ automation_candidate: e.target.checked })} />
        Automation candidate
      </label>
      {sources.length > 0 && (
        <>
          <span className="field-label">Link to requirements</span>
          <div className="inline-actions" style={{ flexWrap: "wrap", margin: "6px 0 12px" }}>
            {sources.map((k) => (
              <label key={k} style={{ display: "flex", gap: 6 }}>
                <input type="checkbox" checked={p.requirement_keys.includes(k)}
                  onChange={() => set({ requirement_keys: p.requirement_keys.includes(k)
                    ? p.requirement_keys.filter((x) => x !== k) : [...p.requirement_keys, k] })} />
                <span className="mono">{k}</span>
              </label>
            ))}
          </div>
        </>
      )}
      <div className="inline-actions">
        <button className="primary" disabled={save.isPending || !p.title.trim() || steps.length === 0} onClick={() => save.mutate()}>
          Save
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

function RejectDialog({ s, onClose, onDone }: { s: Suggestion; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const reject = useMutation({
    mutationFn: () => http.post(`/ee/ai/suggestions/${s.id}/reject`, { reason: reason.trim() || null }),
    onSuccess: () => { toast("Suggestion rejected"); onDone(); },
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title="Reject suggestion" onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>{s.payload.title}</p>
      <Field label="Reason (optional)" hint="Helps the team see why it was left out.">
        <input value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} placeholder="Out of scope, duplicate, wrong behaviour…" />
      </Field>
      <div className="inline-actions">
        <button className="danger" disabled={reject.isPending} onClick={() => reject.mutate()}>Reject</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}
