import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Attempt, CycleTestRow, Paginated, TestCase } from "../api/types";
import { Badge, Card, EmptyState, errText, useToast } from "../ui";

const RESULTS = ["passed", "failed", "blocked", "skipped"] as const;

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
  const cases = useQuery({
    queryKey: ["testcases-all", pid],
    queryFn: () => http.get<Paginated<TestCase>>(`/projects/${pid}/test-cases?page_size=200`),
    enabled: !!pid,
  });
  const nameFor = (id: string) => cases.data?.items.find((t) => t.id === id);

  return (
    <>
      <div className="page-header">
        <h2>Execution Runner</h2>
      </div>
      <div className="grid" style={{ gridTemplateColumns: "320px 1fr" }}>
        <Card>
          <h3 style={{ marginTop: 0 }}>Cycle tests</h3>
          {cts.data?.items.length ? (
            <div className="stack">
              {cts.data.items.map((ct) => {
                const tc = nameFor(ct.test_case_id);
                return (
                  <button
                    key={ct.id}
                    style={{ width: "100%", textAlign: "left" }}
                    className={activeCt === ct.id ? "primary" : ""}
                    onClick={() => setActiveCt(ct.id)}
                  >
                    <div className="key">{tc?.key ?? ct.test_case_id.slice(0, 8)}</div>
                    <div>{tc?.title}</div>
                    <Badge value={ct.displayed_result} />
                  </button>
                );
              })}
            </div>
          ) : (
            <EmptyState>No cycle tests.</EmptyState>
          )}
        </Card>

        {activeCt ? (
          <AttemptPanel
            key={activeCt}
            cycleTestId={activeCt}
            existingAttemptId={
              cts.data?.items.find((c) => c.id === activeCt)?.in_progress_attempt_id ??
              cts.data?.items.find((c) => c.id === activeCt)?.authoritative_attempt_id ??
              null
            }
            onChanged={() => qc.invalidateQueries({ queryKey: ["cycle-tests", cycleId] })}
            toastError={(e) => toast(errText(e), "error")}
          />
        ) : (
          <Card>
            <EmptyState>Select a cycle test to begin.</EmptyState>
          </Card>
        )}
      </div>
    </>
  );
}

function AttemptPanel({
  cycleTestId,
  existingAttemptId,
  onChanged,
  toastError,
}: {
  cycleTestId: string;
  existingAttemptId: string | null;
  onChanged: () => void;
  toastError: (e: unknown) => void;
}) {
  const qc = useQueryClient();
  const [attemptId, setAttemptId] = useState<string | null>(existingAttemptId);
  const toast = useToast();

  const attempt = useQuery({
    queryKey: ["attempt", attemptId],
    queryFn: () => http.get<Attempt>(`/attempts/${attemptId}`),
    enabled: !!attemptId,
  });

  const start = useMutation({
    mutationFn: () => http.post<Attempt>(`/cycle-tests/${cycleTestId}/attempts`),
    onSuccess: (a) => {
      setAttemptId(a.id);
      qc.invalidateQueries({ queryKey: ["attempt", a.id] });
      onChanged();
    },
    onError: toastError,
  });

  const setStep = useMutation({
    mutationFn: ({ order, result }: { order: number; result: string }) =>
      http.patch<Attempt>(`/attempts/${attemptId}/steps/${order}`, { result }),
    onSuccess: (a) => qc.setQueryData(["attempt", attemptId], a),
    onError: toastError,
  });

  const complete = useMutation({
    mutationFn: () => http.post<Attempt>(`/attempts/${attemptId}/complete`, {}),
    onSuccess: (a) => {
      qc.setQueryData(["attempt", attemptId], a);
      onChanged();
      toast(`Attempt ${a.overall_result}`);
    },
    onError: toastError,
  });

  useEffect(() => setAttemptId(existingAttemptId), [existingAttemptId]);

  const a = attempt.data;
  const inProgress = a?.status === "IN_PROGRESS";

  return (
    <Card>
      <div className="page-header">
        <h3 style={{ margin: 0 }}>Attempt</h3>
        <div className="inline-actions">
          {!inProgress && (
            <button className="primary" onClick={() => start.mutate()}>
              {a ? "Start new attempt / retest" : "Start attempt"}
            </button>
          )}
          {inProgress && (
            <button className="primary" onClick={() => complete.mutate()}>
              Complete attempt
            </button>
          )}
        </div>
      </div>

      {!a && <EmptyState>No attempt yet.</EmptyState>}
      {a && (
        <>
          <p>
            <Badge value={a.status} />{" "}
            {a.overall_result && <Badge value={a.overall_result} />}{" "}
            <span className="muted">
              {a.environment} / {a.build}
            </span>
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Action</th>
                  <th>Expected</th>
                  <th>Result</th>
                </tr>
              </thead>
              <tbody>
                {a.steps.map((s) => (
                  <tr key={s.order_index}>
                    <td>
                      {s.order_index}
                      {s.is_required ? "" : " (opt)"}
                    </td>
                    <td style={{ whiteSpace: "normal" }}>{s.action}</td>
                    <td style={{ whiteSpace: "normal" }}>{s.expected_result}</td>
                    <td className="inline-actions">
                      {inProgress ? (
                        RESULTS.map((r) => (
                          <button
                            key={r}
                            className={s.result === r ? "primary" : ""}
                            onClick={() => setStep.mutate({ order: s.order_index, result: r })}
                          >
                            {r[0].toUpperCase()}
                          </button>
                        ))
                      ) : (
                        <Badge value={s.result} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {a.corrections.length > 0 && (
            <p className="muted">
              Corrections: {a.corrections.map((c) => `${c.old_value}→${c.new_value}`).join(", ")}
            </p>
          )}
        </>
      )}
    </Card>
  );
}
