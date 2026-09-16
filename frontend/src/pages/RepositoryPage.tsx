import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Paginated, Plan, TestCase, Version } from "../api/types";
import { Badge, Dialog, EmptyState, Field, cap, errText, useToast } from "../ui";
import { StepEditor, type DraftStep } from "../components/StepEditor";
import { Pager, SortHeader, type SortState } from "../components/table";
import { Icons } from "../components/icons";

const PAGE_SIZE = 10;
const STATES = ["draft", "in_review", "approved", "active", "deprecated", "archived"];
const AUTOMATION_STATUSES = ["not_applicable", "candidate", "automated"];

/* -------------------------- workflow transitions -------------------------- */
// Mirrors the backend's exact transition tables (domain/test_case/service.py
// _VERSION_TRANSITIONS / _LOGICAL_TRANSITIONS) so the UI only ever offers a
// move it knows is valid, and bulk actions can silently skip rows for which
// the target isn't reachable from their current state.
const VERSION_MOVES = new Set(["draft>in_review", "in_review>draft", "in_review>approved"]);
const LOGICAL_MOVES = new Set([
  "approved>active", "active>deprecated", "deprecated>active",
  "active>archived", "deprecated>archived", "approved>archived",
  "draft>archived", "in_review>archived", "archived>draft",
]);

function transitionTestCase(tc: TestCase, to: string) {
  const key = `${tc.lifecycle_state}>${to}`;
  if (VERSION_MOVES.has(key)) {
    return http.post(`/test-cases/${tc.id}/version-transitions`, { to, expected_version: tc.version });
  }
  if (LOGICAL_MOVES.has(key)) {
    return http.post(`/test-cases/${tc.id}/lifecycle-transitions`, { to, expected_version: tc.version });
  }
  return Promise.reject(new Error(`Cannot move from ${tc.lifecycle_state} to ${to}`));
}

function nextActions(tc: TestCase): { label: string; to: string }[] {
  switch (tc.lifecycle_state) {
    case "draft": return [{ label: "Submit for review", to: "in_review" }];
    case "in_review": return [{ label: "Approve version", to: "approved" }, { label: "Request changes", to: "draft" }];
    case "approved": return [{ label: "Activate", to: "active" }];
    case "active": return [{ label: "Deprecate", to: "deprecated" }];
    case "deprecated": return [{ label: "Reinstate", to: "active" }];
    default: return [];
  }
}

export function RepositoryPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [state, setState] = useState("");
  const [planId, setPlanId] = useState("");
  const [idsFilter, setIdsFilter] = useState(params.get("ids") ?? "");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortState>({ field: "created_at", dir: "desc" });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<TestCase | null>(null);
  const [confirm, setConfirm] = useState<{ tc: TestCase; action: "archive" | "restore" } | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkDialog, setBulkDialog] = useState<null | "automation" | "status">(null);

  const plans = useQuery({
    queryKey: ["plans", pid],
    queryFn: () => http.get<Plan[]>(`/projects/${pid}/plans`),
    enabled: !!pid,
  });

  const sortParam = `${sort.dir === "desc" ? "-" : ""}${sort.field}`;
  const list = useQuery({
    queryKey: ["testcases", pid, q, state, planId, idsFilter, page, sortParam],
    queryFn: () =>
      http.get<Paginated<TestCase>>(
        `/projects/${pid}/test-cases?` +
          new URLSearchParams({
            ...(q ? { q } : {}),
            ...(state ? { state } : {}),
            ...(planId === "none" ? { unassigned: "true" } : planId ? { plan_id: planId } : {}),
            ...(idsFilter ? { ids: idsFilter } : {}),
            sort: sortParam,
            page: String(page),
            page_size: String(PAGE_SIZE),
          }).toString(),
      ),
    enabled: !!pid,
  });

  const urlQ = params.get("q");
  useEffect(() => {
    if (urlQ !== null) { setQ(urlQ); setPage(1); }
  }, [urlQ]);

  const clearIdsFilter = () => {
    setIdsFilter("");
    setParams((p) => { p.delete("ids"); return p; }, { replace: true });
  };

  const invalidate = () => qc.invalidateQueries({ queryKey: ["testcases"] });

  const [form, setForm] = useState<{ title: string; description: string; steps: DraftStep[] }>({
    title: "",
    description: "",
    steps: [{ action: "", expected_result: "", is_required: true }],
  });

  const create = useMutation({
    mutationFn: () =>
      http.post(`/projects/${pid}/test-cases`, {
        title: form.title,
        description: form.description,
        steps: form.steps.filter((s) => s.action && s.expected_result),
      }),
    onSuccess: () => {
      invalidate();
      setCreating(false);
      setForm({ title: "", description: "", steps: [{ action: "", expected_result: "", is_required: true }] });
      toast("Test case created");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const lifecycle = useMutation({
    mutationFn: ({ tc, to }: { tc: TestCase; to: string }) =>
      http.post(`/test-cases/${tc.id}/lifecycle-transitions`, { to, expected_version: tc.version }),
    onSuccess: (_d, v) => {
      invalidate();
      setConfirm(null);
      toast(v.to === "archived" ? "Test case archived" : v.to === "draft" ? "Test case restored" : "Test case updated");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const changeStatus = useMutation({
    mutationFn: ({ tc, to }: { tc: TestCase; to: string }) => transitionTestCase(tc, to),
    onSuccess: () => { invalidate(); toast("Status updated"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const setAutomation = useMutation({
    mutationFn: ({ tc, automation_status }: { tc: TestCase; automation_status: string }) =>
      http.post(`/test-cases/${tc.id}/automation-status`, { automation_status, expected_version: tc.version }),
    onSuccess: () => invalidate(),
    onError: (e) => toast(errText(e), "error"),
  });

  const onSort = (s: SortState) => {
    setSort(s);
    setPage(1);
  };
  const goToPage = (p: number) => { setPage(p); setSelected(new Set()); };

  const data = list.data;
  const pageRows = data?.items ?? [];
  const toggleSelect = (id: string) =>
    setSelected((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleSelectAll = () =>
    setSelected((prev) => (prev.size === pageRows.length ? new Set() : new Set(pageRows.map((r) => r.id))));
  const clearSelection = () => setSelected(new Set());

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Test Cases</h2>
          <div className="page-sub">Design, organize, review, and reuse test coverage</div>
        </div>
        <button className="primary" onClick={() => setCreating(true)}>
          + New test case
        </button>
      </div>

      <div className="toolbar">
        <input
          placeholder="Search title or key…"
          value={q}
          onChange={(e) => { setQ(e.target.value); setPage(1); }}
        />
        <select value={state} onChange={(e) => { setState(e.target.value); setPage(1); }}>
          <option value="">Any state</option>
          {STATES.map((s) => (
            <option key={s} value={s}>{cap(s)}</option>
          ))}
        </select>
        <select value={planId} onChange={(e) => { setPlanId(e.target.value); setPage(1); }}>
          <option value="">Any test plan</option>
          <option value="none">— not in a plan —</option>
          {plans.data?.map((p) => (
            <option key={p.id} value={p.id}>{p.key} · {p.name}</option>
          ))}
        </select>
        {idsFilter && (
          <span className="req-chip">
            Linked test cases only
            <button onClick={clearIdsFilter} aria-label="Clear linked-only filter">✕</button>
          </span>
        )}
      </div>

      {list.isLoading ? (
        <p>Loading…</p>
      ) : data && data.items.length > 0 ? (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="checkbox-cell">
                    <input type="checkbox" checked={pageRows.length > 0 && selected.size === pageRows.length} onChange={toggleSelectAll} aria-label="Select all" />
                  </th>
                  <SortHeader label="Key" field="key" sort={sort} onSort={onSort} className="nowrap" />
                  <SortHeader label="Title" field="title" sort={sort} onSort={onSort} />
                  <th className="nowrap">Test Plan</th>
                  <SortHeader label="State" field="state" sort={sort} onSort={onSort} className="nowrap" />
                  <SortHeader label="Automation" field="automation" sort={sort} onSort={onSort} className="nowrap" />
                  <SortHeader label="Created" field="created_at" sort={sort} onSort={onSort} className="nowrap" />
                  <th className="nowrap">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((tc) => (
                  <tr key={tc.id} className={selected.has(tc.id) ? "selected-row" : ""}>
                    <td className="checkbox-cell">
                      <input type="checkbox" checked={selected.has(tc.id)} onChange={() => toggleSelect(tc.id)} aria-label={`Select ${tc.key}`} />
                    </td>
                    <td className="key">
                      <Link to={`/p/${projectKey}/tests/${tc.id}`}>{tc.key}</Link>
                    </td>
                    <td>
                      {tc.title}
                      {tc.has_draft_changes && <span className="stale"> · draft pending</span>}
                    </td>
                    <td className="nowrap">
                      {tc.plan_keys && tc.plan_keys.length > 0
                        ? <span className="key">{tc.plan_keys.join(", ")}</span>
                        : <span className="muted">—</span>}
                    </td>
                    <td className="nowrap">
                      <Badge value={tc.lifecycle_state} />
                    </td>
                    <td className="nowrap">
                      <select
                        className="filter-select"
                        style={{ minWidth: 140 }}
                        value={tc.automation_status}
                        disabled={tc.lifecycle_state === "archived" || setAutomation.isPending}
                        onChange={(e) => setAutomation.mutate({ tc, automation_status: e.target.value })}
                      >
                        {AUTOMATION_STATUSES.map((a) => <option key={a} value={a}>{cap(a)}</option>)}
                      </select>
                    </td>
                    <td className="nowrap muted small">{relDate(tc.created_at)}</td>
                    <td className="nowrap">
                      <div className="row-actions">
                        {nextActions(tc).length > 0 && (
                          <TcStatusMenu actions={nextActions(tc)} onPick={(to) => changeStatus.mutate({ tc, to })} />
                        )}
                        {tc.lifecycle_state !== "archived" && (
                          <button className="icon-btn" title="Edit" onClick={() => setEditing(tc)}>
                            {Icons.edit}
                          </button>
                        )}
                        {tc.lifecycle_state === "archived" ? (
                          <button
                            className="icon-btn"
                            title="Restore"
                            onClick={() => setConfirm({ tc, action: "restore" })}
                          >
                            {Icons.restore}
                          </button>
                        ) : (
                          <button
                            className="icon-btn warn"
                            title="Archive"
                            onClick={() => setConfirm({ tc, action: "archive" })}
                          >
                            {Icons.trash}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager
            page={data.page}
            pages={data.pages ?? 1}
            total={data.total}
            pageSize={data.page_size}
            onPage={goToPage}
          />
        </>
      ) : (
        <EmptyState>No test cases match.</EmptyState>
      )}

      {selected.size > 0 && (
        <div className="bulk-bar">
          <span className="bulk-count">{selected.size} selected</span>
          <button className="sm" onClick={() => setBulkDialog("status")}>{Icons.refresh} Change Status</button>
          <button className="sm" onClick={() => setBulkDialog("automation")}>{Icons.robot} Set Automation</button>
          <span className="spacer-flex" />
          <button className="icon-btn" onClick={clearSelection} aria-label="Clear selection">✕</button>
        </div>
      )}

      {creating && (
        <Dialog title="New test case" onClose={() => setCreating(false)}>
          <Field label="Title">
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} autoFocus />
          </Field>
          <Field label="Description">
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <StepEditor steps={form.steps} onChange={(steps) => setForm({ ...form, steps })} />
          <button
            className="primary"
            style={{ marginTop: 12 }}
            disabled={!form.title || create.isPending}
            onClick={() => create.mutate()}
          >
            Create draft
          </button>
        </Dialog>
      )}

      {editing && (
        <EditTestCaseDialog
          tc={editing}
          plans={plans.data ?? []}
          onClose={() => setEditing(null)}
          onDone={() => {
            invalidate();
            setEditing(null);
          }}
          onChanged={invalidate}
        />
      )}

      {confirm && (
        <Dialog
          title={confirm.action === "archive" ? "Archive test case" : "Restore test case"}
          onClose={() => setConfirm(null)}
        >
          <p>
            {confirm.action === "archive" ? (
              <>
                Archive <strong className="key">{confirm.tc.key}</strong>? Its cycles, executions,
                links and history are preserved — it just leaves normal selection and reports.
              </>
            ) : (
              <>
                Restore <strong className="key">{confirm.tc.key}</strong> to Draft for re-review.
              </>
            )}
          </p>
          <div className="inline-actions" style={{ marginTop: 14 }}>
            <button
              className={confirm.action === "archive" ? "danger" : "primary"}
              onClick={() =>
                lifecycle.mutate({
                  tc: confirm.tc,
                  to: confirm.action === "archive" ? "archived" : "draft",
                })
              }
            >
              {confirm.action === "archive" ? "Archive" : "Restore"}
            </button>
            <button onClick={() => setConfirm(null)}>Cancel</button>
          </div>
        </Dialog>
      )}

      {bulkDialog === "automation" && (
        <BulkAutomationDialog
          onClose={() => setBulkDialog(null)}
          onApply={async (automation_status) => {
            const targets = data?.items.filter((tc) => selected.has(tc.id)) ?? [];
            let ok = 0;
            for (const tc of targets) {
              try {
                await http.post(`/test-cases/${tc.id}/automation-status`, { automation_status, expected_version: tc.version });
                ok++;
              } catch { /* skip - e.g. archived */ }
            }
            invalidate();
            toast(`Updated automation status for ${ok} of ${targets.length} test case(s)`);
            clearSelection();
            setBulkDialog(null);
          }}
        />
      )}

      {bulkDialog === "status" && (
        <BulkStatusDialog
          onClose={() => setBulkDialog(null)}
          onApply={async (to) => {
            const targets = data?.items.filter((tc) => selected.has(tc.id)) ?? [];
            let ok = 0;
            for (const tc of targets) {
              try {
                await transitionTestCase(tc, to);
                ok++;
              } catch { /* not a valid move from this row's current state - skip */ }
            }
            invalidate();
            toast(`Moved ${ok} of ${targets.length} test case(s) to ${cap(to)}${ok < targets.length ? " (others were skipped - not a valid move from their current state)" : ""}`);
            clearSelection();
            setBulkDialog(null);
          }}
        />
      )}
    </>
  );
}

function relDate(iso: string): string {
  const d = new Date(iso);
  const days = (Date.now() - d.getTime()) / 86_400_000;
  if (days < 1) return "Today";
  if (days < 2) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function TcStatusMenu({ actions, onPick }: { actions: { label: string; to: string }[]; onPick: (to: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button className="icon-btn" title="Change status" aria-label="Change status" onClick={() => setOpen((v) => !v)}>
        {Icons.refresh}
      </button>
      {open && (
        <div className="app-menu-panel" style={{ position: "absolute", right: 0, top: "100%", marginTop: 6, padding: 6, minWidth: 170, zIndex: 10 }}>
          {actions.map((a) => (
            <button key={a.to} className="ghost sm" style={{ display: "block", width: "100%", textAlign: "left" }}
              onClick={() => { onPick(a.to); setOpen(false); }}>
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function BulkAutomationDialog({ onClose, onApply }: { onClose: () => void; onApply: (v: string) => Promise<void> }) {
  const [value, setValue] = useState("candidate");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog title="Set automation status" onClose={onClose}>
      <Field label="Automation status">
        <select value={value} onChange={(e) => setValue(e.target.value)}>
          {AUTOMATION_STATUSES.map((a) => <option key={a} value={a}>{cap(a)}</option>)}
        </select>
      </Field>
      <div className="inline-actions" style={{ marginTop: 4 }}>
        <button className="primary" disabled={busy} onClick={async () => { setBusy(true); await onApply(value); setBusy(false); }}>
          {busy ? "Applying…" : "Apply"}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

function BulkStatusDialog({ onClose, onApply }: { onClose: () => void; onApply: (to: string) => Promise<void> }) {
  const [value, setValue] = useState("in_review");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog title="Change status" onClose={onClose}>
      <p className="muted small" style={{ marginTop: 0 }}>
        Applies to every selected test case for which this is a valid move from its current
        state; others are left unchanged.
      </p>
      <Field label="Target status">
        <select value={value} onChange={(e) => setValue(e.target.value)}>
          {STATES.map((s) => <option key={s} value={s}>{cap(s)}</option>)}
        </select>
      </Field>
      <div className="inline-actions" style={{ marginTop: 4 }}>
        <button className="primary" disabled={busy} onClick={async () => { setBusy(true); await onApply(value); setBusy(false); }}>
          {busy ? "Applying…" : "Apply"}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

// The three version-level statuses editable in-place (mirrors _VERSION_TRANSITIONS
// in the backend). Active/deprecated/archived are lifecycle states, not offered here -
// they're changed via the row's status menu instead.
const EDITABLE_STATUSES = ["draft", "in_review", "approved"];

function EditTestCaseDialog({
  tc,
  plans,
  onClose,
  onDone,
  onChanged,
}: {
  tc: TestCase;
  plans: Plan[];
  onClose: () => void;
  onDone: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const versions = useQuery({
    queryKey: ["versions", tc.id],
    queryFn: () => http.get<Version[]>(`/test-cases/${tc.id}/versions`),
  });
  const current = versions.data?.[versions.data.length - 1];
  const [form, setForm] = useState<{
    title: string;
    description: string;
    preconditions: string;
    steps: DraftStep[];
    change_summary: string;
  } | null>(null);
  const [status, setStatus] = useState(tc.lifecycle_state);
  const [linkedPlanKeys, setLinkedPlanKeys] = useState<string[]>(tc.plan_keys ?? []);
  const [planPick, setPlanPick] = useState("");

  if (versions.data && current && form === null) {
    setForm({
      title: current.title,
      description: current.description ?? "",
      preconditions: current.preconditions ?? "",
      steps: current.steps.length
        ? current.steps.map((s) => ({ ...s }))
        : [{ action: "", expected_result: "", is_required: true }],
      change_summary: "",
    });
  }

  const canPickStatus = EDITABLE_STATUSES.includes(tc.lifecycle_state);

  const save = useMutation({
    mutationFn: async () => {
      const updated = await http.patch<TestCase>(`/test-cases/${tc.id}`, {
        expected_version: tc.version,
        title: form!.title,
        description: form!.description || null,
        preconditions: form!.preconditions || null,
        steps: form!.steps.filter((s) => s.action && s.expected_result),
        change_summary: form!.change_summary || null,
      });
      if (canPickStatus && status !== tc.lifecycle_state) {
        await transitionTestCase(updated, status);
      }
    },
    onSuccess: () => {
      toast("Test case updated");
      onDone();
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const addToPlan = useMutation({
    mutationFn: (planId: string) => http.post(`/plans/${planId}/scope`, { test_case_ids: [tc.id] }),
    onSuccess: (_d, planId) => {
      const plan = plans.find((p) => p.id === planId);
      if (plan) setLinkedPlanKeys((prev) => (prev.includes(plan.key) ? prev : [...prev, plan.key]));
      setPlanPick("");
      toast("Added to test plan");
      onChanged();
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const availablePlans = plans.filter(
    (p) => (p.status === "draft" || p.status === "active") && !linkedPlanKeys.includes(p.key),
  );

  return (
    <Dialog title={`Edit ${tc.key}`} onClose={onClose}>
      {!form ? (
        <p>Loading…</p>
      ) : (
        <>
          <p className="muted" style={{ marginTop: 0 }}>
            Editing controlled content on an approved / active test case forks a new Draft version;
            existing cycles keep the version they snapshotted.
          </p>
          {canPickStatus && (
            <Field label="Status">
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                {EDITABLE_STATUSES.map((s) => (
                  <option
                    key={s}
                    value={s}
                    disabled={s !== tc.lifecycle_state && !VERSION_MOVES.has(`${tc.lifecycle_state}>${s}`)}
                  >
                    {cap(s)}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field label="Title">
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </Field>
          <Field label="Preconditions">
            <textarea
              value={form.preconditions}
              onChange={(e) => setForm({ ...form, preconditions: e.target.value })}
            />
          </Field>
          <Field label="Description">
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <StepEditor steps={form.steps} onChange={(steps) => setForm({ ...form, steps })} />
          <Field label="Change summary (optional)">
            <input
              value={form.change_summary}
              onChange={(e) => setForm({ ...form, change_summary: e.target.value })}
            />
          </Field>
          <Field label="Test plans">
            {linkedPlanKeys.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
                {linkedPlanKeys.map((k) => (
                  <span key={k} className="req-chip">{k}</span>
                ))}
              </div>
            )}
            <div className="inline-actions">
              <select value={planPick} onChange={(e) => setPlanPick(e.target.value)} style={{ flex: 1 }}>
                <option value="">
                  {availablePlans.length === 0 ? "No plans available to add" : "Choose a test plan…"}
                </option>
                {availablePlans.map((p) => (
                  <option key={p.id} value={p.id}>{p.key} · {p.name}</option>
                ))}
              </select>
              <button
                className="sm"
                disabled={!planPick || addToPlan.isPending}
                onClick={() => addToPlan.mutate(planPick)}
              >
                Add
              </button>
            </div>
          </Field>
          <button
            className="primary"
            style={{ marginTop: 12 }}
            disabled={!form.title || save.isPending}
            onClick={() => save.mutate()}
          >
            Save changes
          </button>
        </>
      )}
    </Dialog>
  );
}
