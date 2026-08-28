import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Cycle, Paginated, Plan, TestCase } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";

export function CyclesPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [scopeFor, setScopeFor] = useState<Cycle | null>(null);
  const [form, setForm] = useState({ plan_id: "", name: "", environment: "staging", build: "1" });

  const plans = useQuery({
    queryKey: ["plans", pid],
    queryFn: () => http.get<Plan[]>(`/projects/${pid}/plans`),
    enabled: !!pid,
  });
  const cycles = useQuery({
    queryKey: ["cycles", pid],
    queryFn: () => http.get<Cycle[]>(`/projects/${pid}/cycles`),
    enabled: !!pid,
  });

  const create = useMutation({
    mutationFn: () =>
      http.post(`/plans/${form.plan_id}/cycles`, {
        name: form.name,
        environment: form.environment,
        build: form.build,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cycles"] });
      setCreating(false);
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const transition = useMutation({
    mutationFn: ({ cycle, to }: { cycle: Cycle; to: string }) =>
      http.post(`/cycles/${cycle.id}/transitions`, {
        to,
        expected_version: cycle.version,
        reason: "via UI",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cycles"] });
      toast("Cycle updated");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <h2>Cycles</h2>
        <button className="primary" onClick={() => setCreating(true)} disabled={!plans.data?.length}>
          New cycle
        </button>
      </div>

      {cycles.data && cycles.data.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Key</th>
                <th>Name</th>
                <th>Env / Build</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {cycles.data.map((c) => (
                <tr key={c.id}>
                  <td className="key">{c.key}</td>
                  <td>{c.name}</td>
                  <td>
                    {c.environment} / {c.build}
                  </td>
                  <td>
                    <Badge value={c.status} />
                  </td>
                  <td className="inline-actions">
                    {c.status === "draft" && (
                      <>
                        <button onClick={() => setScopeFor(c)}>Add tests</button>
                        <button onClick={() => transition.mutate({ cycle: c, to: "active" })}>
                          Activate
                        </button>
                      </>
                    )}
                    {(c.status === "active" || c.status === "reopened") && (
                      <>
                        <Link className="btn" to={`/p/${projectKey}/cycles/${c.id}/run`}>
                          Run
                        </Link>
                        <button onClick={() => transition.mutate({ cycle: c, to: "completed" })}>
                          Complete
                        </button>
                      </>
                    )}
                    {c.status === "completed" && (
                      <button onClick={() => transition.mutate({ cycle: c, to: "reopened" })}>
                        Reopen
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState>No cycles yet. Create a plan first, then a cycle.</EmptyState>
      )}

      {creating && (
        <Dialog title="New cycle" onClose={() => setCreating(false)}>
          <Field label="Plan">
            <select
              value={form.plan_id}
              onChange={(e) => setForm({ ...form, plan_id: e.target.value })}
            >
              <option value="">Select…</option>
              {plans.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.key} — {p.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Name">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <div className="field-row">
            <Field label="Environment">
              <input
                value={form.environment}
                onChange={(e) => setForm({ ...form, environment: e.target.value })}
              />
            </Field>
            <Field label="Build">
              <input value={form.build} onChange={(e) => setForm({ ...form, build: e.target.value })} />
            </Field>
          </div>
          <button
            className="primary"
            disabled={!form.plan_id || !form.name}
            onClick={() => create.mutate()}
          >
            Create
          </button>
        </Dialog>
      )}

      {scopeFor && pid && (
        <CycleScopeDialog cycle={scopeFor} projectId={pid} onClose={() => setScopeFor(null)} />
      )}
    </>
  );
}

function CycleScopeDialog({
  cycle,
  projectId,
  onClose,
}: {
  cycle: Cycle;
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
  const add = useMutation({
    mutationFn: () => http.post(`/cycles/${cycle.id}/tests`, { test_case_ids: [...selected] }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["cycles"] });
      toast("Tests added");
      onClose();
    },
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title={`Add tests to ${cycle.key}`} onClose={onClose}>
      <p className="muted">Only test cases with an approved version can be activated in a cycle.</p>
      <div className="table-wrap" style={{ maxHeight: 320, overflowY: "auto" }}>
        <table>
          <tbody>
            {cases.data?.items
              .filter((tc) => ["approved", "active"].includes(tc.lifecycle_state))
              .map((tc) => (
                <tr key={tc.id}>
                  <td>
                    <input
                      type="checkbox"
                      style={{ width: "auto" }}
                      checked={selected.has(tc.id)}
                      onChange={(e) => {
                        const n = new Set(selected);
                        e.target.checked ? n.add(tc.id) : n.delete(tc.id);
                        setSelected(n);
                      }}
                    />
                  </td>
                  <td className="key">{tc.key}</td>
                  <td>{tc.title}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <button
        className="primary"
        style={{ marginTop: 12 }}
        disabled={selected.size === 0}
        onClick={() => add.mutate()}
      >
        Add {selected.size}
      </button>
    </Dialog>
  );
}
