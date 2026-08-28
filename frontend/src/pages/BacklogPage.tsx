import { useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Defect, Paginated, Release, Requirement, TestCase } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";
import { Pager, SortHeader, sortBy, type SortState } from "../components/table";

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

export function BacklogPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [dialog, setDialog] = useState<null | "requirement" | "defect" | "link">(null);

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
    onSuccess: invalidateAll,
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <h2>Requirements &amp; Defects</h2>
        <div className="inline-actions">
          <button onClick={() => setDialog("requirement")}>New requirement</button>
          <button onClick={() => setDialog("defect")}>New defect</button>
          <button className="primary" onClick={() => setDialog("link")}>
            Link requirement → test case
          </button>
        </div>
      </div>

      <div className="stack">
        <Listing
          title="Requirements"
          accent="var(--sec-backlog)"
          defaultSort="key"
          rows={reqs.data?.items ?? []}
          columns={[
            { key: "key", label: "Key", className: "key nowrap", render: (r: Requirement) => r.key },
            { key: "title", label: "Title", render: (r: Requirement) => r.title },
            { key: "priority", label: "Priority", className: "nowrap", render: (r: Requirement) => <Badge value={r.priority} /> },
            { key: "status", label: "Status", className: "nowrap", render: (r: Requirement) => <Badge value={r.status} /> },
            {
              key: "actions", label: "Actions", sortable: false, className: "nowrap",
              render: (r: Requirement) =>
                r.status === "draft" ? (
                  <button className="sm" onClick={() => transition.mutate({ kind: "requirements", id: r.id, version: r.version, to: "active" })}>
                    Activate
                  </button>
                ) : null,
            },
          ]}
        />

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
      </div>

      {dialog && dialog !== "link" && (
        <CreateDialog
          kind={dialog}
          projectId={pid!}
          releases={releases.data?.items ?? []}
          onClose={() => setDialog(null)}
          onDone={() => {
            invalidateAll();
            setDialog(null);
          }}
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
    </>
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
    onSuccess: onDone,
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
