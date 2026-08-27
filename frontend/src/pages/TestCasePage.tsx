import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import type { TestCase, Version } from "../api/types";
import { Badge, Card, EmptyState, errText, useToast } from "../ui";

const NEXT_VERSION: Record<string, string> = {
  draft: "in_review",
  in_review: "approved",
};

export function TestCasePage() {
  const { testCaseId } = useParams();
  const qc = useQueryClient();
  const toast = useToast();

  const tc = useQuery({
    queryKey: ["testcase", testCaseId],
    queryFn: () => http.get<TestCase>(`/test-cases/${testCaseId}`),
  });
  const versions = useQuery({
    queryKey: ["versions", testCaseId],
    queryFn: () => http.get<Version[]>(`/test-cases/${testCaseId}/versions`),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["testcase", testCaseId] });
    qc.invalidateQueries({ queryKey: ["versions", testCaseId] });
    qc.invalidateQueries({ queryKey: ["testcases"] });
  };

  const versionTransition = useMutation({
    mutationFn: (to: string) =>
      http.post(`/test-cases/${testCaseId}/version-transitions`, {
        to,
        expected_version: tc.data!.version,
      }),
    onSuccess: () => {
      invalidate();
      toast("Workflow updated");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const lifecycleTransition = useMutation({
    mutationFn: (to: string) =>
      http.post(`/test-cases/${testCaseId}/lifecycle-transitions`, {
        to,
        expected_version: tc.data!.version,
      }),
    onSuccess: () => {
      invalidate();
      toast("Lifecycle updated");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  if (tc.isLoading || !tc.data) return <p>Loading…</p>;
  const t = tc.data;
  const current = versions.data?.find((v) => v.id === t.current_version_id);

  return (
    <>
      <div className="page-header">
        <div>
          <h2>
            <span className="key">{t.key}</span> — {t.title}
          </h2>
          <div className="inline-actions" style={{ marginTop: 6 }}>
            <Badge value={t.lifecycle_state} />
            {t.has_draft_changes && <span className="stale">draft changes pending review</span>}
          </div>
        </div>
        <div className="inline-actions">
          {current && NEXT_VERSION[current.status] && (
            <button
              className="primary"
              onClick={() => versionTransition.mutate(NEXT_VERSION[current.status])}
            >
              {current.status === "draft" ? "Submit for review" : "Approve version"}
            </button>
          )}
          {current?.status === "in_review" && (
            <button onClick={() => versionTransition.mutate("draft")}>Request changes</button>
          )}
          {t.lifecycle_state === "approved" && (
            <button className="primary" onClick={() => lifecycleTransition.mutate("active")}>
              Activate
            </button>
          )}
          {t.lifecycle_state === "active" && (
            <button onClick={() => lifecycleTransition.mutate("deprecated")}>Deprecate</button>
          )}
        </div>
      </div>

      <div className="grid cols-2">
        {versions.data?.map((v) => (
          <Card key={v.id}>
            <div className="page-header">
              <h3 style={{ margin: 0 }}>
                v{v.version_number} <Badge value={v.status} />
              </h3>
              {v.id === t.approved_version_id && <span className="badge approved">approved</span>}
            </div>
            {v.description && <p className="muted">{v.description}</p>}
            {v.preconditions && (
              <p>
                <strong>Preconditions:</strong> {v.preconditions}
              </p>
            )}
            <ol>
              {v.steps.map((s, i) => (
                <li key={i}>
                  {s.action} → <em>{s.expected_result}</em>
                  {!s.is_required && <span className="muted"> (optional)</span>}
                </li>
              ))}
            </ol>
            {v.change_summary && <p className="muted">Change: {v.change_summary}</p>}
          </Card>
        ))}
        {versions.data?.length === 0 && <EmptyState>No versions.</EmptyState>}
      </div>
    </>
  );
}
