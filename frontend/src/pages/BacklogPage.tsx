import { useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Defect, Paginated, Release } from "../api/types";
import { Badge, Dialog, EmptyState, Field, cap, errText, useToast } from "../ui";
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
  const [dialog, setDialog] = useState<null | "defect">(null);

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

  const invalidateAll = () => qc.invalidateQueries({ queryKey: ["defects"] });

  const transition = useMutation({
    mutationFn: ({ id, version, to }: { id: string; version: number; to: string }) =>
      http.post(`/defects/${id}/transitions`, { to, expected_version: version }),
    onSuccess: (_d, v) => { invalidateAll(); toast(`Status changed to ${cap(v.to)}`); },
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Defects</h2>
          <div className="page-sub">Track defects raised against this project</div>
        </div>
        <div className="inline-actions">
          <button className="primary" onClick={() => setDialog("defect")}>New defect</button>
        </div>
      </div>

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
                <button className="sm" onClick={() => transition.mutate({ id: d.id, version: d.version, to: "open" })}>
                  Open
                </button>
              ) : null,
          },
        ]}
      />

      {dialog === "defect" && (
        <CreateDefectDialog
          projectId={pid!}
          releases={releases.data?.items ?? []}
          onClose={() => setDialog(null)}
          onDone={() => { invalidateAll(); setDialog(null); }}
        />
      )}
    </>
  );
}

const SEVERITIES = ["critical", "high", "major", "minor", "trivial"];

function CreateDefectDialog({
  projectId, releases, onClose, onDone,
}: {
  projectId: string;
  releases: Release[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState({ summary: "", severity: "major", release_id: "" });
  const m = useMutation({
    mutationFn: () =>
      http.post(`/projects/${projectId}/defects`, {
        summary: f.summary,
        severity: f.severity,
        release_id: f.release_id || null,
      }),
    onSuccess: () => { toast("Defect created"); onDone(); },
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title="New defect" onClose={onClose}>
      <Field label="Summary">
        <input value={f.summary} onChange={(e) => setF({ ...f, summary: e.target.value })} autoFocus />
      </Field>
      <Field label="Severity">
        <select value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}>
          {SEVERITIES.map((s) => <option key={s} value={s}>{cap(s)}</option>)}
        </select>
      </Field>
      <Field label="Release (optional)">
        <select value={f.release_id} onChange={(e) => setF({ ...f, release_id: e.target.value })}>
          <option value="">None</option>
          {releases.map((r) => (
            <option key={r.id} value={r.id}>
              {r.key} — {r.name}
            </option>
          ))}
        </select>
      </Field>
      <div className="inline-actions" style={{ marginTop: 4 }}>
        <button className="primary" disabled={!f.summary.trim() || m.isPending} onClick={() => m.mutate()}>
          {m.isPending ? "Creating…" : "Create defect"}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}
