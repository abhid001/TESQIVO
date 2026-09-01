import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Attempt, Cycle, CycleTestRow } from "../api/types";
import { Badge, Card, Dialog, EmptyState, Field, errText, useToast } from "../ui";

const RESULTS = [
  { key: "passed", label: "Pass" },
  { key: "failed", label: "Fail" },
  { key: "blocked", label: "Blocked" },
  { key: "skipped", label: "Skip" },
] as const;

export function CycleRunnerPage() {
  const { cycleId, projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [activeCt, setActiveCt] = useState<string | null>(null);

  const cts = useQuery({
    queryKey: ["cycle-tests", cycleId],
    queryFn: () => http.get<{ items: CycleTestRow[] }>(`/cycles/${cycleId}/tests`),
    enabled: !!cycleId,
    refetchInterval: 8000,
  });
  const cycles = useQuery({
    queryKey: ["cycles", pid],
    queryFn: () => http.get<Cycle[]>(`/projects/${pid}/cycles`),
    enabled: !!pid,
  });
  const cycle = cycles.data?.find((c) => c.id === cycleId);

  const items = cts.data?.items ?? [];
  const active = items.find((c) => c.id === activeCt) ?? null;

  return (
    <>
      <div className="page-header">
        <div>
          <Link to={`/p/${projectKey}/cycles`} className="btn sm" style={{ marginBottom: 8 }}>
            ← Back to Executions
          </Link>
          <h2 style={{ margin: 0 }}>Execution Runner</h2>
          <div className="page-sub">
            {cycle ? (
              <>
                <span className="key">{cycle.key}</span> · {cycle.name} · {cycle.environment} / {cycle.build}
              </>
            ) : (
              "Loading cycle…"
            )}
          </div>
        </div>
      </div>

      <div className="runner-grid">
        <Card>
          <h3 style={{ marginTop: 0 }}>Cycle tests</h3>
          {items.length ? (
            <div className="runner-list">
              {items.map((ct) => (
                <button
                  key={ct.id}
                  className={`runner-item${activeCt === ct.id ? " active" : ""}`}
                  onClick={() => setActiveCt(ct.id)}
                >
                  <div className="r-key">{ct.test_case_key}</div>
                  <div className="r-title">{ct.test_case_title}</div>
                  <Badge value={ct.displayed_result} />
                  {ct.in_progress_attempt_id && (
                    <span className="muted small" style={{ marginLeft: 6 }}>in progress</span>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <EmptyState>No tests in this cycle. Add some from the Executions page.</EmptyState>
          )}
        </Card>

        {active ? (
          <AttemptPanel
            key={active.id}
            cycleTest={active}
            existingAttemptId={active.in_progress_attempt_id ?? active.authoritative_attempt_id ?? null}
            onChanged={() => qc.invalidateQueries({ queryKey: ["cycle-tests", cycleId] })}
            toastError={(e) => toast(errText(e), "error")}
          />
        ) : (
          <Card>
            <EmptyState>Select a test on the left to begin.</EmptyState>
          </Card>
        )}
      </div>
    </>
  );
}

function AttemptPanel({
  cycleTest,
  existingAttemptId,
  onChanged,
  toastError,
}: {
  cycleTest: CycleTestRow;
  existingAttemptId: string | null;
  onChanged: () => void;
  toastError: (e: unknown) => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [attemptId, setAttemptId] = useState<string | null>(existingAttemptId);
  const [comments, setComments] = useState<Record<number, string>>({});
  const [aborting, setAborting] = useState(false);

  useEffect(() => setAttemptId(existingAttemptId), [existingAttemptId]);

  const attempt = useQuery({
    queryKey: ["attempt", attemptId],
    queryFn: () => http.get<Attempt>(`/attempts/${attemptId}`),
    enabled: !!attemptId,
  });
  const a = attempt.data;
  const inProgress = a?.status === "IN_PROGRESS";

  useEffect(() => {
    if (a) setComments(Object.fromEntries(a.steps.map((s) => [s.order_index, s.comment ?? ""])));
  }, [a?.id, a?.steps.length]);

  const start = useMutation({
    mutationFn: () => http.post<Attempt>(`/cycle-tests/${cycleTest.id}/attempts`),
    onSuccess: (att) => {
      setAttemptId(att.id);
      qc.setQueryData(["attempt", att.id], att);
      onChanged();
    },
    onError: toastError,
  });

  const setStep = useMutation({
    mutationFn: ({ order, result, comment }: { order: number; result: string; comment: string }) =>
      http.patch<Attempt>(`/attempts/${attemptId}/steps/${order}`, {
        result,
        comment: comment.trim() || null,
      }),
    onSuccess: (att) => qc.setQueryData(["attempt", attemptId], att),
    onError: toastError,
  });

  const complete = useMutation({
    mutationFn: () => http.post<Attempt>(`/attempts/${attemptId}/complete`, {}),
    onSuccess: (att) => {
      qc.setQueryData(["attempt", attemptId], att);
      onChanged();
      toast(`Attempt ${att.overall_result}`);
    },
    onError: toastError,
  });

  const abort = useMutation({
    mutationFn: (reason: string) => http.post<Attempt>(`/attempts/${attemptId}/abort`, { reason }),
    onSuccess: (att) => {
      qc.setQueryData(["attempt", attemptId], att);
      setAborting(false);
      onChanged();
      toast("Attempt aborted");
    },
    onError: toastError,
  });

  const requiredPending = useMemo(
    () => (a?.steps ?? []).filter((s) => s.is_required && (!s.result || s.result === "not_run")).length,
    [a],
  );

  return (
    <Card>
      <div className="page-header">
        <div>
          <h3 style={{ margin: 0 }}>{cycleTest.test_case_key}</h3>
          <div className="page-sub">{cycleTest.test_case_title}</div>
        </div>
        <div className="inline-actions">
          {!inProgress && (
            <button className="primary" disabled={start.isPending} onClick={() => start.mutate()}>
              {a ? "Start new attempt / retest" : "Start attempt"}
            </button>
          )}
          {inProgress && (
            <>
              <button
                className="primary"
                disabled={complete.isPending || requiredPending > 0}
                title={requiredPending > 0 ? `${requiredPending} required step(s) still need a result` : undefined}
                onClick={() => complete.mutate()}
              >
                Complete attempt
              </button>
              <button className="sm" style={{ color: "var(--danger)" }} onClick={() => setAborting(true)}>
                Abort
              </button>
            </>
          )}
        </div>
      </div>

      {!a && <EmptyState>No attempt yet. Click “Start attempt” to run this test.</EmptyState>}

      {a && (
        <>
          <p>
            <Badge value={a.status} />{" "}
            {a.overall_result && <Badge value={a.overall_result} />}{" "}
            <span className="muted">{a.environment} / {a.build}</span>
            {inProgress && requiredPending > 0 && (
              <span className="muted small" style={{ marginLeft: 8 }}>
                {requiredPending} required step(s) pending
              </span>
            )}
          </p>

          <div className="step-editor">
            {a.steps.map((s) => (
              <div className="runner-step" key={s.order_index}>
                <div className="step-row-head">
                  <strong>
                    Step {s.order_index}
                    {s.is_required ? "" : " (optional)"}
                  </strong>
                  {inProgress ? (
                    <div className="result-group">
                      {RESULTS.map((r) => (
                        <button
                          key={r.key}
                          className={`result-btn${s.result === r.key ? ` on-${r.key}` : ""}`}
                          disabled={setStep.isPending}
                          onClick={() =>
                            setStep.mutate({
                              order: s.order_index,
                              result: r.key,
                              comment: comments[s.order_index] ?? s.comment ?? "",
                            })
                          }
                        >
                          {r.label}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <Badge value={s.result} />
                  )}
                </div>
                <div style={{ marginTop: 6, fontSize: 13 }}>
                  <div><span className="muted">Action:</span> {s.action}</div>
                  <div><span className="muted">Expected:</span> {s.expected_result}</div>
                </div>
                {inProgress ? (
                  <textarea
                    className="runner-step-comment"
                    placeholder="Comment / actual result (optional)"
                    value={comments[s.order_index] ?? ""}
                    onChange={(e) =>
                      setComments((c) => ({ ...c, [s.order_index]: e.target.value }))
                    }
                    onBlur={() => {
                      const val = comments[s.order_index] ?? "";
                      if (s.result && s.result !== "not_run" && val.trim() !== (s.comment ?? "").trim()) {
                        setStep.mutate({ order: s.order_index, result: s.result, comment: val });
                      }
                    }}
                  />
                ) : (
                  s.comment && <p className="muted" style={{ margin: "6px 0 0" }}>{s.comment}</p>
                )}
              </div>
            ))}
          </div>

          {a.corrections.length > 0 && (
            <p className="muted" style={{ marginTop: 12 }}>
              Corrections: {a.corrections.map((c) => `${c.old_value}→${c.new_value}`).join(", ")}
            </p>
          )}
        </>
      )}

      {aborting && (
        <AbortDialog
          busy={abort.isPending}
          onClose={() => setAborting(false)}
          onAbort={(reason) => abort.mutate(reason)}
        />
      )}
    </Card>
  );
}

function AbortDialog({
  busy,
  onClose,
  onAbort,
}: {
  busy: boolean;
  onClose: () => void;
  onAbort: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  return (
    <Dialog title="Abort attempt" onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>
        The attempt is discarded and the test keeps its previous result. This can’t be undone.
      </p>
      <Field label="Reason">
        <input value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
      </Field>
      <button className="primary" disabled={!reason.trim() || busy} onClick={() => onAbort(reason.trim())}>
        Abort attempt
      </button>
    </Dialog>
  );
}
