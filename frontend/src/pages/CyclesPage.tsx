import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Cycle, CycleTestRow, Paginated, Plan, TestCase } from "../api/types";
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
      toast("Cycle created");
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
        <div>
          <h2>Test Executions</h2>
          <div className="page-sub">Run manual cycles and track results in real time</div>
        </div>
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
                    {["draft", "active", "reopened"].includes(c.status) && (
                      <button onClick={() => setScopeFor(c)}>Manage tests</button>
                    )}
                    {c.status === "draft" && (
                      <button onClick={() => transition.mutate({ cycle: c, to: "active" })}>
                        Activate
                      </button>
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
                      <>
                        <button onClick={() => setScopeFor(c)}>View tests</button>
                        <button onClick={() => transition.mutate({ cycle: c, to: "reopened" })}>
                          Reopen
                        </button>
                      </>
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
        <CycleTestsDialog cycle={scopeFor} projectId={pid} onClose={() => setScopeFor(null)} />
      )}
    </>
  );
}

function CycleTestsDialog({
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
  const editable = ["draft", "active", "reopened"].includes(cycle.status);
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const current = useQuery({
    queryKey: ["cycle-tests", cycle.id],
    queryFn: () => http.get<{ items: CycleTestRow[] }>(`/cycles/${cycle.id}/tests`),
  });
  const cases = useQuery({
    queryKey: ["testcases-all", projectId],
    queryFn: () => http.get<Paginated<TestCase>>(`/projects/${projectId}/test-cases?page_size=200`),
    enabled: adding,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["cycle-tests", cycle.id] });
    qc.invalidateQueries({ queryKey: ["cycles"] });
    qc.invalidateQueries({ queryKey: ["summary"] });
    qc.invalidateQueries({ queryKey: ["cycle-breakdown"] });
  };

  const add = useMutation({
    mutationFn: () => http.post(`/cycles/${cycle.id}/tests`, { test_case_ids: [...selected] }),
    onSuccess: () => {
      refresh();
      setSelected(new Set());
      setAdding(false);
      toast("Tests added");
    },
    onError: (e) => toast(errText(e), "error"),
  });
  const remove = useMutation({
    mutationFn: (ctId: string) => http.del(`/cycle-tests/${ctId}`),
    onSuccess: () => {
      refresh();
      toast("Test removed");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const inCycle = new Set(current.data?.items.map((i) => i.test_case_id));

  return (
    <Dialog title={`Tests in ${cycle.key} — ${cycle.name}`} onClose={onClose}>
      {!editable && (
        <p className="notice info">
          This cycle is {cycle.status}. Reopen it to add or remove tests.
        </p>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="nowrap">Key</th>
              <th>Title</th>
              <th className="nowrap">Result</th>
              {editable && <th className="nowrap">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {current.data?.items.length ? (
              current.data.items.map((ct) => (
                <tr key={ct.id}>
                  <td className="key">{ct.test_case_key}</td>
                  <td>{ct.test_case_title}</td>
                  <td><Badge value={ct.displayed_result} /></td>
                  {editable && (
                    <td className="nowrap">
                      <button
                        className="sm"
                        style={{ color: "var(--danger)" }}
                        disabled={remove.isPending || !!ct.in_progress_attempt_id}
                        title={ct.in_progress_attempt_id ? "An attempt is in progress" : "Remove from cycle"}
                        onClick={() => remove.mutate(ct.id)}
                      >
                        Remove
                      </button>
                    </td>
                  )}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={editable ? 4 : 3} className="muted" style={{ padding: 16 }}>
                  No tests in this cycle yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {editable && !adding && (
        <button className="primary" style={{ marginTop: 14 }} onClick={() => setAdding(true)}>
          + Add tests
        </button>
      )}

      {editable && adding && (
        <div style={{ marginTop: 14 }}>
          <p className="muted">
            Approved / active test cases only. Adding to a running cycle snapshots the approved version immediately.
          </p>
          <div className="table-wrap" style={{ maxHeight: 300, overflowY: "auto" }}>
            <table>
              <tbody>
                {cases.data?.items
                  .filter((tc) => ["approved", "active"].includes(tc.lifecycle_state) && !inCycle.has(tc.id))
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
          <div className="inline-actions" style={{ marginTop: 12 }}>
            <button className="primary" disabled={selected.size === 0 || add.isPending} onClick={() => add.mutate()}>
              Add {selected.size || ""}
            </button>
            <button onClick={() => { setAdding(false); setSelected(new Set()); }}>Cancel</button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
