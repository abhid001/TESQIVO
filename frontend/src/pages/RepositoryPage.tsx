import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Paginated, Plan, Scenario, TestCase, Version } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";
import { StepEditor, type DraftStep } from "../components/StepEditor";
import { Pager, SortHeader, type SortState } from "../components/table";
import { Icons } from "../components/icons";

const PAGE_SIZE = 20;
const STATES = ["draft", "in_review", "approved", "active", "deprecated", "archived"];

export function RepositoryPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [state, setState] = useState("");
  const [planId, setPlanId] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortState>({ field: "key", dir: "asc" });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<TestCase | null>(null);
  const [confirm, setConfirm] = useState<{ tc: TestCase; action: "archive" | "restore" } | null>(null);

  const scenarios = useQuery({
    queryKey: ["scenarios", pid, ""],
    queryFn: () => http.get<{ items: Scenario[] }>(`/projects/${pid}/scenarios`),
    enabled: !!pid,
  });
  const plans = useQuery({
    queryKey: ["plans", pid],
    queryFn: () => http.get<Plan[]>(`/projects/${pid}/plans`),
    enabled: !!pid,
  });

  const sortParam = `${sort.dir === "desc" ? "-" : ""}${sort.field}`;
  const list = useQuery({
    queryKey: ["testcases", pid, q, state, planId, page, sortParam],
    queryFn: () =>
      http.get<Paginated<TestCase>>(
        `/projects/${pid}/test-cases?` +
          new URLSearchParams({
            ...(q ? { q } : {}),
            ...(state ? { state } : {}),
            ...(planId === "none" ? { unassigned: "true" } : planId ? { plan_id: planId } : {}),
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

  const invalidate = () => qc.invalidateQueries({ queryKey: ["testcases"] });

  const [form, setForm] = useState<{ title: string; description: string; scenario_id: string; steps: DraftStep[] }>({
    title: "",
    description: "",
    scenario_id: "",
    steps: [{ action: "", expected_result: "", is_required: true }],
  });

  const create = useMutation({
    mutationFn: () =>
      http.post(`/projects/${pid}/test-cases`, {
        title: form.title,
        description: form.description,
        scenario_id: form.scenario_id || null,
        steps: form.steps.filter((s) => s.action && s.expected_result),
      }),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["scenarios"] });
      setCreating(false);
      setForm({ title: "", description: "", scenario_id: "", steps: [{ action: "", expected_result: "", is_required: true }] });
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

  const onSort = (s: SortState) => {
    setSort(s);
    setPage(1);
  };

  if (!project) return <p>Loading…</p>;
  const data = list.data;

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
            <option key={s}>{s}</option>
          ))}
        </select>
        <select value={planId} onChange={(e) => { setPlanId(e.target.value); setPage(1); }}>
          <option value="">Any test plan</option>
          <option value="none">— not in a plan —</option>
          {plans.data?.map((p) => (
            <option key={p.id} value={p.id}>{p.key} · {p.name}</option>
          ))}
        </select>
      </div>

      {list.isLoading ? (
        <p>Loading…</p>
      ) : data && data.items.length > 0 ? (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <SortHeader label="Key" field="key" sort={sort} onSort={onSort} className="nowrap" />
                  <SortHeader label="Title" field="title" sort={sort} onSort={onSort} />
                  <th className="nowrap">Test Plan</th>
                  <SortHeader label="State" field="state" sort={sort} onSort={onSort} className="nowrap" />
                  <SortHeader label="Automation" field="automation" sort={sort} onSort={onSort} className="nowrap" />
                  <th className="nowrap">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((tc) => (
                  <tr key={tc.id}>
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
                    <td>
                      <Badge value={tc.lifecycle_state} />
                    </td>
                    <td>{tc.automation_status}</td>
                    <td className="nowrap">
                      <div className="inline-actions">
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
            onPage={setPage}
          />
        </>
      ) : (
        <EmptyState>No test cases match.</EmptyState>
      )}

      {creating && (
        <Dialog title="New test case" onClose={() => setCreating(false)}>
          <Field label="Title">
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </Field>
          <Field label="Description">
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <Field label="Scenario (optional)">
            <select value={form.scenario_id} onChange={(e) => setForm({ ...form, scenario_id: e.target.value })}>
              <option value="">— none —</option>
              {scenarios.data?.items.filter((s) => s.status === "active").map((s) => (
                <option key={s.id} value={s.id}>{s.key} · {s.title}</option>
              ))}
            </select>
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
          onClose={() => setEditing(null)}
          onDone={() => {
            invalidate();
            setEditing(null);
          }}
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
    </>
  );
}

function EditTestCaseDialog({
  tc,
  onClose,
  onDone,
}: {
  tc: TestCase;
  onClose: () => void;
  onDone: () => void;
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

  const save = useMutation({
    mutationFn: () =>
      http.patch(`/test-cases/${tc.id}`, {
        expected_version: tc.version,
        title: form!.title,
        description: form!.description || null,
        preconditions: form!.preconditions || null,
        steps: form!.steps.filter((s) => s.action && s.expected_result),
        change_summary: form!.change_summary || null,
      }),
    onSuccess: () => {
      toast("Test case updated");
      onDone();
    },
    onError: (e) => toast(errText(e), "error"),
  });

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
