import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Paginated, Plan, TestCase } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";

export function PlansPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [scopeFor, setScopeFor] = useState<Plan | null>(null);

  const plans = useQuery({
    queryKey: ["plans", pid],
    queryFn: () => http.get<Plan[]>(`/projects/${pid}/plans`),
    enabled: !!pid,
  });

  const create = useMutation({
    mutationFn: () => http.post(`/projects/${pid}/plans`, { name }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plans"] });
      setCreating(false);
      setName("");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const transition = useMutation({
    mutationFn: ({ plan, to }: { plan: Plan; to: string }) =>
      http.post(`/plans/${plan.id}/transitions`, { to, expected_version: plan.version, reason: "via UI" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plans"] }),
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <h2>Plans</h2>
        <button className="primary" onClick={() => setCreating(true)}>
          New plan
        </button>
      </div>
      {plans.data && plans.data.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Key</th>
                <th>Name</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {plans.data.map((p) => (
                <tr key={p.id}>
                  <td className="key">{p.key}</td>
                  <td>{p.name}</td>
                  <td>
                    <Badge value={p.status} />
                  </td>
                  <td className="inline-actions">
                    <button onClick={() => setScopeFor(p)}>Scope</button>
                    {p.status === "draft" && (
                      <button onClick={() => transition.mutate({ plan: p, to: "active" })}>
                        Activate
                      </button>
                    )}
                    {p.status === "active" && (
                      <button onClick={() => transition.mutate({ plan: p, to: "completed" })}>
                        Complete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState>No plans yet.</EmptyState>
      )}

      {creating && (
        <Dialog title="New plan" onClose={() => setCreating(false)}>
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <button className="primary" disabled={!name} onClick={() => create.mutate()}>
            Create
          </button>
        </Dialog>
      )}

      {scopeFor && pid && (
        <ScopeDialog planId={scopeFor.id} projectId={pid} onClose={() => setScopeFor(null)} />
      )}
    </>
  );
}

function ScopeDialog({
  planId,
  projectId,
  onClose,
}: {
  planId: string;
  projectId: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const cases = useQuery({
    queryKey: ["testcases-all", projectId],
    queryFn: () => http.get<Paginated<TestCase>>(`/projects/${projectId}/test-cases?page_size=200`),
  });
  const scope = useQuery({
    queryKey: ["plan-scope", planId],
    queryFn: () => http.get<{ items: { test_case_id: string }[] }>(`/plans/${planId}/scope`),
  });
  const inScope = new Set(scope.data?.items.map((i) => i.test_case_id));

  const add = useMutation({
    mutationFn: () =>
      http.post(`/plans/${planId}/scope`, { test_case_ids: [...selected] }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["plan-scope", planId] });
      setSelected(new Set());
      toast("Scope updated");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  return (
    <Dialog title="Plan scope" onClose={onClose}>
      <div className="table-wrap" style={{ maxHeight: 320, overflowY: "auto" }}>
        <table>
          <tbody>
            {cases.data?.items.map((tc) => (
              <tr key={tc.id}>
                <td>
                  <input
                    type="checkbox"
                    style={{ width: "auto" }}
                    disabled={inScope.has(tc.id)}
                    checked={inScope.has(tc.id) || selected.has(tc.id)}
                    onChange={(e) => {
                      const n = new Set(selected);
                      e.target.checked ? n.add(tc.id) : n.delete(tc.id);
                      setSelected(n);
                    }}
                  />
                </td>
                <td className="key">{tc.key}</td>
                <td>{tc.title}</td>
                <td>
                  <Badge value={tc.lifecycle_state} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        className="primary"
        style={{ marginTop: 12 }}
        disabled={selected.size === 0 || add.isPending}
        onClick={() => add.mutate()}
      >
        Add {selected.size} to scope
      </button>
    </Dialog>
  );
}
