import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Cycle, CycleTestRow, Paginated, Plan, ReferenceValue, Release, TestCase } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";

export function CyclesPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [scopeFor, setScopeFor] = useState<Cycle | null>(null);
  const [cloneFor, setCloneFor] = useState<Cycle | null>(null);
  const [form, setForm] = useState({ plan_id: "", name: "", environment: "", release_id: "", build: "1" });

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
  const refs = useQuery({
    queryKey: ["refs", pid],
    queryFn: () => http.get<ReferenceValue[]>(`/projects/${pid}/reference-values`),
    enabled: !!pid,
  });
  const releases = useQuery({
    queryKey: ["releases", pid],
    queryFn: () => http.get<Paginated<Release>>(`/projects/${pid}/releases?page_size=200`),
    enabled: !!pid,
  });
  const environments = (refs.data ?? []).filter((r) => r.kind === "environment" && r.is_active);
  const releaseName = (id: string | null) =>
    id ? releases.data?.items.find((r) => r.id === id)?.key ?? "" : "";

  const refresh = () => qc.invalidateQueries({ queryKey: ["cycles"] });

  const create = useMutation({
    mutationFn: () =>
      http.post(`/plans/${form.plan_id}/cycles`, {
        name: form.name,
        environment: form.environment || "default",
        build: form.build,
        release_id: form.release_id || null,
      }),
    onSuccess: () => { refresh(); setCreating(false); toast("Cycle created"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const clone = useMutation({
    mutationFn: (v: { id: string; name: string; environment: string; build: string }) =>
      http.post(`/cycles/${v.id}/clone`, { name: v.name, environment: v.environment, build: v.build }),
    onSuccess: () => { refresh(); setCloneFor(null); toast("Cycle cloned to a new draft"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const transition = useMutation({
    mutationFn: ({ cycle, to }: { cycle: Cycle; to: string }) =>
      http.post(`/cycles/${cycle.id}/transitions`, { to, expected_version: cycle.version, reason: "via UI" }),
    onSuccess: () => { refresh(); toast("Cycle updated"); },
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
                <th className="nowrap">Env / Build</th>
                <th className="nowrap">Release</th>
                <th className="nowrap">Status</th>
                <th className="nowrap">Actions</th>
              </tr>
            </thead>
            <tbody>
              {cycles.data.map((c) => (
                <tr key={c.id}>
                  <td className="key">{c.key}</td>
                  <td>{c.name}</td>
                  <td className="nowrap">{c.environment} / {c.build}</td>
                  <td className="nowrap">{releaseName(c.release_id) || <span className="muted">—</span>}</td>
                  <td className="nowrap"><Badge value={c.status} /></td>
                  <td className="nowrap">
                    <div className="inline-actions">
                      {["draft", "active", "reopened"].includes(c.status) && (
                        <button className="sm" onClick={() => setScopeFor(c)}>Manage tests</button>
                      )}
                      {c.status === "draft" && (
                        <button className="sm" onClick={() => transition.mutate({ cycle: c, to: "active" })}>Activate</button>
                      )}
                      {(c.status === "active" || c.status === "reopened") && (
                        <>
                          <Link className="btn sm primary" to={`/p/${projectKey}/cycles/${c.id}/run`}>Run</Link>
                          <button className="sm" onClick={() => transition.mutate({ cycle: c, to: "completed" })}>Complete</button>
                        </>
                      )}
                      {c.status === "completed" && (
                        <>
                          <button className="sm" onClick={() => setScopeFor(c)}>View tests</button>
                          <button className="sm" onClick={() => transition.mutate({ cycle: c, to: "reopened" })}>Reopen</button>
                        </>
                      )}
                      <button className="sm" title="Create a draft copy of this cycle" onClick={() => setCloneFor(c)}>Clone</button>
                    </div>
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
            <select value={form.plan_id} onChange={(e) => setForm({ ...form, plan_id: e.target.value })}>
              <option value="">Select…</option>
              {plans.data?.map((p) => <option key={p.id} value={p.id}>{p.key} — {p.name}</option>)}
            </select>
          </Field>
          <Field label="Name">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus />
          </Field>
          <div className="field-row">
            <Field label="Environment">
              <select value={form.environment} onChange={(e) => setForm({ ...form, environment: e.target.value })}>
                <option value="">— select —</option>
                {environments.map((env) => (
                  <option key={env.id} value={env.value}>
                    {env.value[0].toUpperCase() + env.value.slice(1)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Build">
              <input value={form.build} onChange={(e) => setForm({ ...form, build: e.target.value })} />
            </Field>
          </div>
          <Field label="Release (optional)">
            <select value={form.release_id} onChange={(e) => setForm({ ...form, release_id: e.target.value })}>
              <option value="">— none —</option>
              {releases.data?.items.map((r) => (
                <option key={r.id} value={r.id}>{r.key} — {r.name}</option>
              ))}
            </select>
          </Field>
          {environments.length === 0 && (
            <p className="muted small">
              No environments configured — an administrator can add them in Admin console → Projects → Environments.
            </p>
          )}
          <button
            className="primary"
            disabled={!form.plan_id || !form.name || !form.environment || create.isPending}
            onClick={() => create.mutate()}
          >
            Create
          </button>
        </Dialog>
      )}

      {cloneFor && (
        <CloneCycleDialog
          cycle={cloneFor}
          environments={environments}
          busy={clone.isPending}
          onClose={() => setCloneFor(null)}
          onClone={(name, environment, build) => clone.mutate({ id: cloneFor.id, name, environment, build })}
        />
      )}

      {scopeFor && pid && (
        <CycleTestsDialog cycle={scopeFor} projectId={pid} onClose={() => setScopeFor(null)} />
      )}
    </>
  );
}

function CloneCycleDialog({
  cycle, environments, busy, onClose, onClone,
}: {
  cycle: Cycle;
  environments: ReferenceValue[];
  busy: boolean;
  onClose: () => void;
  onClone: (name: string, environment: string, build: string) => void;
}) {
  const [name, setName] = useState(`${cycle.name} (copy)`);
  const [environment, setEnvironment] = useState(cycle.environment);
  const [build, setBuild] = useState(cycle.build);
  const opts = useMemo(() => {
    const vals = environments.map((e) => e.value);
    return vals.includes(cycle.environment) ? vals : [cycle.environment, ...vals];
  }, [environments, cycle.environment]);
  return (
    <Dialog title={`Clone ${cycle.key}`} onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>
        Creates a new <strong>draft</strong> cycle in the same plan with the same test cases — results start fresh.
      </p>
      <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} autoFocus /></Field>
      <div className="field-row">
        <Field label="Environment">
          <select value={environment} onChange={(e) => setEnvironment(e.target.value)}>
            {opts.map((v) => <option key={v} value={v}>{v[0].toUpperCase() + v.slice(1)}</option>)}
          </select>
        </Field>
        <Field label="Build"><input value={build} onChange={(e) => setBuild(e.target.value)} /></Field>
      </div>
      <button className="primary" disabled={!name.trim() || busy} onClick={() => onClone(name, environment, build)}>
        Clone cycle
      </button>
    </Dialog>
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
    onSuccess: () => { refresh(); setSelected(new Set()); setAdding(false); toast("Tests added"); },
    onError: (e) => toast(errText(e), "error"),
  });
  const remove = useMutation({
    mutationFn: (ctId: string) => http.del(`/cycle-tests/${ctId}`),
    onSuccess: () => { refresh(); toast("Test removed"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const inCycle = new Set(current.data?.items.map((i) => i.test_case_id));
  const eligible = (cases.data?.items ?? []).filter(
    (tc) => ["approved", "active"].includes(tc.lifecycle_state) && !inCycle.has(tc.id),
  );
  const allSelected = eligible.length > 0 && eligible.every((tc) => selected.has(tc.id));
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(eligible.map((tc) => tc.id)));

  return (
    <Dialog title={`Tests in ${cycle.key} — ${cycle.name}`} onClose={onClose}>
      {!editable && (
        <p className="notice info">This cycle is {cycle.status}. Reopen it to add or remove tests.</p>
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
        <button className="primary" style={{ marginTop: 14 }} onClick={() => setAdding(true)}>+ Add tests</button>
      )}

      {editable && adding && (
        <div style={{ marginTop: 14 }}>
          <p className="muted small">
            Approved / active test cases only. Adding to a running cycle snapshots the approved version immediately.
          </p>
          {cases.isLoading ? (
            <p>Loading test cases…</p>
          ) : eligible.length === 0 ? (
            <p className="muted">No eligible test cases to add.</p>
          ) : (
            <div className="table-wrap" style={{ maxHeight: 320, overflowY: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th style={{ width: 34 }}>
                      <input
                        type="checkbox"
                        style={{ width: "auto" }}
                        checked={allSelected}
                        onChange={toggleAll}
                        aria-label="Select all"
                      />
                    </th>
                    <th className="nowrap">Key</th>
                    <th>Title</th>
                  </tr>
                </thead>
                <tbody>
                  {eligible.map((tc) => (
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
          )}
          <div className="inline-actions" style={{ marginTop: 12 }}>
            <button className="primary" disabled={selected.size === 0 || add.isPending} onClick={() => add.mutate()}>
              Add {selected.size || ""} {selected.size === 1 ? "test" : "tests"}
            </button>
            <button onClick={() => { setAdding(false); setSelected(new Set()); }}>Cancel</button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
