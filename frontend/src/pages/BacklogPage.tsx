import { useEffect, useState, type ReactNode } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { ActivityItem, Defect, Member, Paginated, Release, Requirement, TestCase } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";
import { Pager, SortHeader, sortBy, type SortState } from "../components/table";
import { Icons } from "../components/icons";

const PRIORITIES = ["critical", "high", "medium", "low"];
const REQ_TYPES = ["functional", "non_functional", "compliance", "ux", "performance", "security"];
const SOURCE_TYPES = ["manual", "import", "jira", "confluence", "email", "other"];
const NEXT_STATUS: Record<string, string[]> = {
  draft: ["active", "archived"],
  active: ["fulfilled", "archived"],
  fulfilled: ["active", "archived"],
  archived: ["draft"],
};

const PAGE = 20;

interface Col<T> {
  key: string;
  label: string;
  sortable?: boolean;
  value?: (r: T) => unknown;
  render: (r: T) => ReactNode;
  className?: string;
}

function Listing<T extends { id: string }>({
  title,
  accent,
  rows,
  columns,
  defaultSort,
}: {
  title: string;
  accent: string;
  rows: T[];
  columns: Col<T>[];
  defaultSort: string;
}) {
  const [sort, setSort] = useState<SortState>({ field: defaultSort, dir: "asc" });
  const [page, setPage] = useState(1);
  const col = columns.find((c) => c.key === sort.field) ?? columns[0];
  const getter = col.value ?? ((r: T) => (r as Record<string, unknown>)[col.key]);
  const sorted = sortBy(rows, getter, sort.dir);
  const pageRows = sorted.slice((page - 1) * PAGE, page * PAGE);
  const pages = Math.max(1, Math.ceil(sorted.length / PAGE));

  return (
    <section>
      <h3 className="section-title" style={{ ["--dot" as string]: accent }}>
        {title} <span className="muted" style={{ fontWeight: 400 }}>({rows.length})</span>
      </h3>
      {rows.length === 0 ? (
        <EmptyState>Nothing here yet.</EmptyState>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {columns.map((c) =>
                    c.sortable === false ? (
                      <th key={c.key} className={c.className}>{c.label}</th>
                    ) : (
                      <SortHeader
                        key={c.key}
                        label={c.label}
                        field={c.key}
                        sort={sort}
                        onSort={(s) => { setSort(s); setPage(1); }}
                        className={c.className}
                      />
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((r) => (
                  <tr key={r.id}>
                    {columns.map((c) => (
                      <td key={c.key} className={c.className}>{c.render(r)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pages={pages} total={sorted.length} pageSize={PAGE} onPage={setPage} />
        </>
      )}
    </section>
  );
}

export function BacklogPage({ view = "both" }: { view?: "requirements" | "defects" | "both" }) {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [dialog, setDialog] = useState<null | "requirement" | "defect" | "link">(null);
  const [editReq, setEditReq] = useState<Requirement | null>(null);
  const [delReq, setDelReq] = useState<Requirement | null>(null);

  const reqs = useQuery({
    queryKey: ["reqs", pid],
    queryFn: () => http.get<Paginated<Requirement>>(`/projects/${pid}/requirements?page_size=200`),
    enabled: !!pid,
  });
  const releases = useQuery({
    queryKey: ["releases", pid],
    queryFn: () => http.get<Paginated<Release>>(`/projects/${pid}/releases?page_size=200`),
    enabled: !!pid,
  });
  const defects = useQuery({
    queryKey: ["defects", pid],
    queryFn: () => http.get<Paginated<Defect>>(`/projects/${pid}/defects?page_size=200`),
    enabled: !!pid,
  });
  const members = useQuery({
    queryKey: ["members", pid],
    queryFn: () => http.get<Member[]>(`/projects/${pid}/members`),
    enabled: !!pid,
  });
  const cases = useQuery({
    queryKey: ["testcases-all", pid],
    queryFn: () => http.get<Paginated<TestCase>>(`/projects/${pid}/test-cases?page_size=200`),
    enabled: !!pid,
  });

  const invalidateAll = () =>
    ["reqs", "releases", "defects", "matrix"].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );

  const transition = useMutation({
    mutationFn: ({ kind, id, version, to }: { kind: string; id: string; version: number; to: string }) =>
      http.post(`/${kind}/${id}/transitions`, { to, expected_version: version }),
    onSuccess: (_d, v) => { invalidateAll(); toast(`Status changed to ${v.to}`); },
    onError: (e) => toast(errText(e), "error"),
  });
  const removeReq = useMutation({
    mutationFn: (id: string) => http.del(`/requirements/${id}`),
    onSuccess: () => { invalidateAll(); setDelReq(null); toast("Requirement deleted"); },
    onError: (e) => toast(errText(e), "error"),
  });

  // deep-link from the traceability matrix: ?req=DEMO-REQ-1 opens that requirement
  const focusKey = params.get("req");
  useEffect(() => {
    if (!focusKey || !reqs.data) return;
    const found = reqs.data.items.find((r) => r.key === focusKey);
    if (found) setEditReq(found);
    setParams((p) => { p.delete("req"); return p; }, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusKey, reqs.data]);

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <div>
          <h2>{view === "defects" ? "Defects" : "Requirements"}</h2>
          <div className="page-sub">
            {view === "defects"
              ? "Track defects raised against this project"
              : "Manage product requirements and their test coverage"}
          </div>
        </div>
        <div className="inline-actions">
          {view !== "defects" && <button onClick={() => setDialog("requirement")}>New requirement</button>}
          <button onClick={() => setDialog("defect")}>New defect</button>
          {view !== "defects" && (
            <button className="primary" onClick={() => setDialog("link")}>
              Link requirement → test case
            </button>
          )}
        </div>
      </div>

      <div className="stack">
        {view !== "defects" && (
        <Listing
          title="Requirements"
          accent="var(--sec-backlog)"
          defaultSort="key"
          rows={reqs.data?.items ?? []}
          columns={[
            { key: "key", label: "Key", className: "key nowrap", render: (r: Requirement) => r.key },
            {
              key: "title", label: "Title",
              render: (r: Requirement) => (
                <>
                  {r.title}
                  {r.labels && <div className="muted small">{r.labels}</div>}
                </>
              ),
            },
            { key: "owner_name", label: "Owner", className: "nowrap", render: (r: Requirement) => r.owner_name ?? <span className="muted">—</span> },
            { key: "priority", label: "Priority", className: "nowrap", render: (r: Requirement) => <Badge value={r.priority} /> },
            { key: "status", label: "Status", className: "nowrap", render: (r: Requirement) => <Badge value={r.status} /> },
            {
              key: "actions", label: "Actions", sortable: false, className: "nowrap",
              render: (r: Requirement) => (
                <div className="inline-actions">
                  {r.status === "draft" && (
                    <button className="sm" onClick={() => transition.mutate({ kind: "requirements", id: r.id, version: r.version, to: "active" })}>
                      Activate
                    </button>
                  )}
                  <button className="icon-btn" title="Edit" onClick={() => setEditReq(r)}>{Icons.edit}</button>
                  <button className="icon-btn warn" title="Delete" onClick={() => setDelReq(r)}>{Icons.trash}</button>
                </div>
              ),
            },
          ]}
        />
        )}

        {view !== "requirements" && (
        <Listing
          title="Defects"
          accent="var(--sec-traceability)"
          defaultSort="key"
          rows={defects.data?.items ?? []}
          columns={[
            { key: "key", label: "Key", className: "key nowrap", render: (d: Defect) => d.key },
            { key: "summary", label: "Summary", render: (d: Defect) => d.summary },
            { key: "severity", label: "Severity", className: "nowrap", render: (d: Defect) => <Badge value={d.severity} /> },
            { key: "status", label: "Status", className: "nowrap", render: (d: Defect) => <Badge value={d.status} /> },
            {
              key: "actions", label: "Actions", sortable: false, className: "nowrap",
              render: (d: Defect) =>
                d.status === "new" ? (
                  <button className="sm" onClick={() => transition.mutate({ kind: "defects", id: d.id, version: d.version, to: "open" })}>
                    Open
                  </button>
                ) : null,
            },
          ]}
        />
        )}
      </div>

      {dialog === "defect" && (
        <CreateDialog
          kind="defect"
          projectId={pid!}
          releases={releases.data?.items ?? []}
          onClose={() => setDialog(null)}
          onDone={() => {
            invalidateAll();
            setDialog(null);
          }}
        />
      )}
      {dialog === "requirement" && (
        <RequirementFormDialog
          projectId={pid!}
          releases={releases.data?.items ?? []}
          members={members.data ?? []}
          onClose={() => setDialog(null)}
          onDone={() => { invalidateAll(); setDialog(null); }}
        />
      )}
      {dialog === "link" && (
        <LinkDialog
          projectId={pid!}
          requirements={reqs.data?.items ?? []}
          testCases={cases.data?.items ?? []}
          onClose={() => setDialog(null)}
          onDone={() => {
            qc.invalidateQueries({ queryKey: ["matrix"] });
            setDialog(null);
          }}
        />
      )}
      {editReq && (
        <RequirementFormDialog
          req={editReq}
          projectId={pid!}
          releases={releases.data?.items ?? []}
          members={members.data ?? []}
          onClose={() => setEditReq(null)}
          onDone={() => { invalidateAll(); setEditReq(null); }}
        />
      )}
      {delReq && (
        <Dialog title="Delete requirement" onClose={() => setDelReq(null)}>
          <p>
            Delete <strong className="key">{delReq.key}</strong> — “{delReq.title}”? This removes it and
            its trace links permanently. This cannot be undone.
          </p>
          <div className="inline-actions" style={{ marginTop: 14 }}>
            <button className="danger" disabled={removeReq.isPending} onClick={() => removeReq.mutate(delReq.id)}>Delete</button>
            <button onClick={() => setDelReq(null)}>Cancel</button>
          </div>
        </Dialog>
      )}
    </>
  );
}

function RequirementFormDialog({
  req, projectId, releases, members, onClose, onDone,
}: {
  req?: Requirement;
  projectId: string;
  releases: Release[];
  members: Member[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const editing = !!req;
  const [f, setF] = useState({
    title: req?.title ?? "",
    description: req?.description ?? "",
    acceptance_criteria: req?.acceptance_criteria ?? "",
    priority: req?.priority ?? "medium",
    status: req?.status ?? "draft",
    req_type: req?.req_type ?? "functional",
    owner_id: req?.owner_id ?? "",
    component: req?.component ?? "",
    labels: req?.labels ?? "",
    source_type: req?.source_type ?? "manual",
    external_reference: req?.external_reference ?? "",
    release_id: req?.release_id ?? "",
  });
  const [showHistory, setShowHistory] = useState(false);

  const statusOptions = editing
    ? [req!.status, ...(NEXT_STATUS[req!.status] ?? [])]
    : ["draft", "active"];

  const history = useQuery({
    queryKey: ["req-history", req?.id],
    queryFn: () => http.get<{ items: ActivityItem[] }>(`/requirements/${req!.id}/history`),
    enabled: editing && showHistory,
  });

  const save = useMutation({
    mutationFn: () => {
      if (!editing) {
        return http.post(`/projects/${projectId}/requirements`, {
          title: f.title,
          description: f.description || null,
          acceptance_criteria: f.acceptance_criteria || null,
          priority: f.priority,
          status: f.status,
          req_type: f.req_type,
          owner_id: f.owner_id || null,
          component: f.component || null,
          labels: f.labels || null,
          source_type: f.source_type,
          external_reference: f.external_reference || null,
          release_id: f.release_id || null,
        });
      }
      return http.patch(`/requirements/${req!.id}`, {
        expected_version: req!.version,
        title: f.title,
        description: f.description,
        acceptance_criteria: f.acceptance_criteria,
        priority: f.priority,
        status: f.status,
        req_type: f.req_type,
        component: f.component,
        labels: f.labels,
        source_type: f.source_type,
        external_reference: f.external_reference,
        ...(f.owner_id ? { owner_id: f.owner_id } : { clear_owner: true }),
        ...(f.release_id ? { release_id: f.release_id } : { clear_release: true }),
      });
    },
    onSuccess: () => { toast(editing ? "Requirement saved" : "Requirement created"); onDone(); },
    onError: (e) => toast(errText(e), "error"),
  });

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value });

  return (
    <Dialog title={editing ? `Edit ${req!.key}` : "New requirement"} onClose={onClose}>
      <Field label="Title"><input value={f.title} onChange={set("title")} autoFocus /></Field>
      <Field label="Description">
        <textarea value={f.description} onChange={set("description")} rows={3} placeholder="What must the product do?" />
      </Field>
      <Field label="Acceptance criteria">
        <textarea value={f.acceptance_criteria} onChange={set("acceptance_criteria")} rows={3} placeholder="Given / when / then, or a checklist of conditions" />
      </Field>
      <div className="field-row">
        <Field label="Priority">
          <select value={f.priority} onChange={set("priority")}>
            {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select value={f.status} onChange={set("status")}>
            {statusOptions.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Type">
          <select value={f.req_type} onChange={set("req_type")}>
            {REQ_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
          </select>
        </Field>
      </div>
      <div className="field-row">
        <Field label="Owner">
          <select value={f.owner_id} onChange={set("owner_id")}>
            <option value="">— unassigned —</option>
            {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.username}</option>)}
          </select>
        </Field>
        <Field label="Release">
          <select value={f.release_id} onChange={set("release_id")}>
            <option value="">— none —</option>
            {releases.map((r) => <option key={r.id} value={r.id}>{r.key} — {r.name}</option>)}
          </select>
        </Field>
      </div>
      <div className="field-row">
        <Field label="Component"><input value={f.component} onChange={set("component")} placeholder="e.g. checkout" /></Field>
        <Field label="Labels (comma-separated)"><input value={f.labels} onChange={set("labels")} placeholder="pci, must-have" /></Field>
      </div>
      <div className="field-row">
        <Field label="Source">
          <select value={f.source_type} onChange={set("source_type")}>
            {SOURCE_TYPES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Reference / link"><input value={f.external_reference} onChange={set("external_reference")} placeholder="ticket URL or doc id" /></Field>
      </div>

      <div className="inline-actions" style={{ marginTop: 4 }}>
        <button className="primary" disabled={!f.title.trim() || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : editing ? "Save changes" : "Create requirement"}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>

      {editing && (
        <div style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
          <button className="btn sm ghost" onClick={() => setShowHistory((v) => !v)}>
            {showHistory ? "Hide history" : "Show change history"}
          </button>
          {showHistory && (
            <div className="activity" style={{ marginTop: 8 }}>
              {history.isLoading && <p className="muted small">Loading…</p>}
              {(history.data?.items ?? []).map((it) => (
                <div key={it.id} className="activity-item">
                  <div className="activity-body">
                    <div>{it.text}</div>
                    <div className="muted small">{it.actor} · {new Date(it.at).toLocaleString()}</div>
                  </div>
                </div>
              ))}
              {history.data && history.data.items.length === 0 && <p className="muted small">No history.</p>}
            </div>
          )}
        </div>
      )}
    </Dialog>
  );
}

function CreateDialog({
  kind,
  projectId,
  releases,
  onClose,
  onDone,
}: {
  kind: "requirement" | "release" | "defect";
  projectId: string;
  releases: Release[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState<Record<string, string>>({ severity: "major" });
  const path =
    kind === "requirement"
      ? `/projects/${projectId}/requirements`
      : kind === "release"
        ? `/projects/${projectId}/releases`
        : `/projects/${projectId}/defects`;
  const m = useMutation({
    mutationFn: () =>
      http.post(path, {
        title: f.title,
        name: f.name,
        summary: f.summary,
        severity: f.severity,
        release_id: f.release_id || null,
      }),
    onSuccess: () => { toast(`${kind[0].toUpperCase()}${kind.slice(1)} created`); onDone(); },
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title={`New ${kind}`} onClose={onClose}>
      {kind === "requirement" && (
        <Field label="Title">
          <input onChange={(e) => setF({ ...f, title: e.target.value })} />
        </Field>
      )}
      {kind === "release" && (
        <Field label="Name">
          <input onChange={(e) => setF({ ...f, name: e.target.value })} />
        </Field>
      )}
      {kind === "defect" && (
        <>
          <Field label="Summary">
            <input onChange={(e) => setF({ ...f, summary: e.target.value })} />
          </Field>
          <Field label="Severity">
            <select value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}>
              {["critical", "high", "major", "minor", "trivial"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
        </>
      )}
      {kind !== "release" && (
        <Field label="Release (optional)">
          <select onChange={(e) => setF({ ...f, release_id: e.target.value })}>
            <option value="">none</option>
            {releases.map((r) => (
              <option key={r.id} value={r.id}>
                {r.key} — {r.name}
              </option>
            ))}
          </select>
        </Field>
      )}
      <button className="primary" onClick={() => m.mutate()} disabled={m.isPending}>
        Create
      </button>
    </Dialog>
  );
}

function LinkDialog({
  projectId,
  requirements,
  testCases,
  onClose,
  onDone,
}: {
  projectId: string;
  requirements: Requirement[];
  testCases: TestCase[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [req, setReq] = useState("");
  const [tc, setTc] = useState("");
  const m = useMutation({
    mutationFn: () =>
      http.post(`/projects/${projectId}/trace-links`, {
        source_type: "requirement",
        source_id: req,
        target_type: "test_case",
        target_id: tc,
      }),
    onSuccess: () => {
      toast("Linked");
      onDone();
    },
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title="Link requirement → test case" onClose={onClose}>
      <Field label="Requirement">
        <select value={req} onChange={(e) => setReq(e.target.value)}>
          <option value="">Select…</option>
          {requirements.map((r) => (
            <option key={r.id} value={r.id}>
              {r.key} — {r.title}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Test case">
        <select value={tc} onChange={(e) => setTc(e.target.value)}>
          <option value="">Select…</option>
          {testCases.map((t) => (
            <option key={t.id} value={t.id}>
              {t.key} — {t.title}
            </option>
          ))}
        </select>
      </Field>
      <button className="primary" disabled={!req || !tc} onClick={() => m.mutate()}>
        Create link
      </button>
    </Dialog>
  );
}
