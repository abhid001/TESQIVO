import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Paginated, Requirement, Scenario, TestCase } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";
import { Icons } from "../components/icons";

export function ScenariosPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [dialog, setDialog] = useState<{ mode: "create" } | { mode: "edit"; scenario: Scenario } | null>(null);
  const [manage, setManage] = useState<Scenario | null>(null);
  const [q, setQ] = useState("");

  const scenarios = useQuery({
    queryKey: ["scenarios", pid, q],
    queryFn: () => http.get<{ items: Scenario[] }>(`/projects/${pid}/scenarios${q ? `?q=${encodeURIComponent(q)}` : ""}`),
    enabled: !!pid,
  });
  const reqs = useQuery({
    queryKey: ["reqs", pid],
    queryFn: () => http.get<Paginated<Requirement>>(`/projects/${pid}/requirements?page_size=200`),
    enabled: !!pid,
  });
  const reqById = Object.fromEntries((reqs.data?.items ?? []).map((r) => [r.id, r]));

  const refresh = () => {
    ["scenarios", "testcases", "summary", "matrix"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  };

  const setStatus = useMutation({
    mutationFn: ({ s, status }: { s: Scenario; status: string }) =>
      http.post(`/scenarios/${s.id}/status`, { expected_version: s.version, status }),
    onSuccess: (_d, v) => { refresh(); toast(v.status === "archived" ? "Scenario archived" : "Scenario restored"); },
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;
  const items = scenarios.data?.items ?? [];

  return (
    <>
      <div className="page-header">
        <h2>Scenarios</h2>
        <button className="primary" onClick={() => setDialog({ mode: "create" })}>+ New scenario</button>
      </div>

      <p className="muted">
        A scenario groups the test cases that exercise one requirement — the
        <strong> Requirement → Scenario → Test case</strong> flow.
      </p>

      <div className="toolbar">
        <input placeholder="Search scenarios…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {items.length === 0 ? (
        <EmptyState>No scenarios yet.</EmptyState>
      ) : (
        <div className="stack">
          {items.map((s) => (
            <div key={s.id} className="card" style={{ display: "grid", gap: 10 }}>
              <div className="cycle-row-head">
                <span className="key">{s.key}</span>
                <span className="cycle-name">{s.title}</span>
                <Badge value={s.status} />
                <span className="badge">{s.test_count} test cases</span>
                {s.requirement_id && reqById[s.requirement_id] && (
                  <span className="badge" style={{ color: "var(--sec-backlog)" }}>
                    ↳ {reqById[s.requirement_id].key} {reqById[s.requirement_id].title}
                  </span>
                )}
                <div className="inline-actions" style={{ marginLeft: "auto" }}>
                  <button className="sm" onClick={() => setManage(s)}>Manage test cases</button>
                  <button className="icon-btn" title="Edit" onClick={() => setDialog({ mode: "edit", scenario: s })}>
                    {Icons.edit}
                  </button>
                  {s.status === "active" ? (
                    <button className="icon-btn warn" title="Archive" onClick={() => setStatus.mutate({ s, status: "archived" })}>
                      {Icons.trash}
                    </button>
                  ) : (
                    <button className="icon-btn" title="Restore" onClick={() => setStatus.mutate({ s, status: "active" })}>
                      {Icons.restore}
                    </button>
                  )}
                </div>
              </div>
              {s.description && <p className="muted" style={{ margin: 0 }}>{s.description}</p>}
            </div>
          ))}
        </div>
      )}

      {dialog && pid && (
        <ScenarioDialog
          projectId={pid}
          scenario={dialog.mode === "edit" ? dialog.scenario : null}
          requirements={reqs.data?.items ?? []}
          onClose={() => setDialog(null)}
          onDone={() => { refresh(); setDialog(null); }}
        />
      )}
      {manage && pid && (
        <ManageScenarioTests
          projectId={pid}
          projectKey={projectKey!}
          scenario={manage}
          onClose={() => setManage(null)}
          onChanged={refresh}
        />
      )}
    </>
  );
}

function ScenarioDialog({
  projectId, scenario, requirements, onClose, onDone,
}: {
  projectId: string;
  scenario: Scenario | null;
  requirements: Requirement[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState({
    title: scenario?.title ?? "",
    description: scenario?.description ?? "",
    requirement_id: scenario?.requirement_id ?? "",
  });
  const m = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        title: f.title,
        description: f.description || null,
      };
      if (scenario) {
        body.expected_version = scenario.version;
        if (f.requirement_id) body.requirement_id = f.requirement_id;
        else body.clear_requirement = true;
        return http.patch(`/scenarios/${scenario.id}`, body);
      }
      body.requirement_id = f.requirement_id || null;
      return http.post(`/projects/${projectId}/scenarios`, body);
    },
    onSuccess: () => { toast(scenario ? "Scenario saved" : "Scenario created"); onDone(); },
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title={scenario ? `Edit ${scenario.key}` : "New scenario"} onClose={onClose}>
      <Field label="Title">
        <input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} autoFocus />
      </Field>
      <Field label="Requirement (optional)">
        <select value={f.requirement_id} onChange={(e) => setF({ ...f, requirement_id: e.target.value })}>
          <option value="">— none —</option>
          {requirements.map((r) => (
            <option key={r.id} value={r.id}>{r.key} — {r.title}</option>
          ))}
        </select>
      </Field>
      <Field label="Description (optional)">
        <textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
      </Field>
      <button className="primary" disabled={!f.title || m.isPending} onClick={() => m.mutate()}>
        {scenario ? "Save changes" : "Create scenario"}
      </button>
    </Dialog>
  );
}

function ManageScenarioTests({
  projectId, projectKey, scenario, onClose, onChanged,
}: {
  projectId: string;
  projectKey: string;
  scenario: Scenario;
  onClose: () => void;
  onChanged: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const members = useQuery({
    queryKey: ["scenario-tests", scenario.id],
    queryFn: () => http.get<{ items: { id: string; key: string; title: string; lifecycle_state: string }[] }>(`/scenarios/${scenario.id}/test-cases`),
  });
  const unassigned = useQuery({
    queryKey: ["unassigned-tests", projectId],
    queryFn: () => http.get<Paginated<TestCase>>(`/projects/${projectId}/test-cases?unassigned=true&page_size=200`),
    enabled: adding,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["scenario-tests", scenario.id] });
    qc.invalidateQueries({ queryKey: ["unassigned-tests"] });
    onChanged();
  };

  const assign = useMutation({
    mutationFn: (test_case_id: string) =>
      http.post("/scenarios/assign-test-case", { test_case_id, scenario_id: scenario.id }),
  });
  const unassign = useMutation({
    mutationFn: (test_case_id: string) =>
      http.post("/scenarios/assign-test-case", { test_case_id, scenario_id: null }),
    onSuccess: () => { refresh(); toast("Test case removed from scenario"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const addSelected = async () => {
    try {
      for (const id of selected) await assign.mutateAsync(id);
      toast(`${selected.size} test case(s) added`);
      setSelected(new Set());
      setAdding(false);
      refresh();
    } catch (e) {
      toast(errText(e), "error");
    }
  };

  return (
    <Dialog title={`${scenario.key} — test cases`} onClose={onClose}>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th className="nowrap">Key</th><th>Title</th><th className="nowrap">State</th><th className="nowrap">Actions</th></tr>
          </thead>
          <tbody>
            {members.data?.items.length ? members.data.items.map((t) => (
              <tr key={t.id}>
                <td className="key"><Link to={`/p/${projectKey}/tests/${t.id}`}>{t.key}</Link></td>
                <td>{t.title}</td>
                <td className="nowrap"><Badge value={t.lifecycle_state} /></td>
                <td className="nowrap">
                  <button className="sm" style={{ color: "var(--danger)" }} onClick={() => unassign.mutate(t.id)}>Remove</button>
                </td>
              </tr>
            )) : (
              <tr><td colSpan={4} className="muted" style={{ padding: 16 }}>No test cases in this scenario yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {!adding ? (
        <button className="primary" style={{ marginTop: 14 }} onClick={() => setAdding(true)}>+ Add test cases</button>
      ) : (
        <div style={{ marginTop: 14 }}>
          <p className="muted">Test cases not yet in a scenario:</p>
          <div className="table-wrap" style={{ maxHeight: 300, overflowY: "auto" }}>
            <table>
              <tbody>
                {unassigned.data?.items.map((tc) => (
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
                {unassigned.data && unassigned.data.items.length === 0 && (
                  <tr><td colSpan={3} className="muted" style={{ padding: 12 }}>Every test case is already in a scenario.</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="inline-actions" style={{ marginTop: 12 }}>
            <button className="primary" disabled={selected.size === 0} onClick={addSelected}>Add {selected.size || ""}</button>
            <button onClick={() => { setAdding(false); setSelected(new Set()); }}>Cancel</button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
