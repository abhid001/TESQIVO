import { useMemo, useRef, useState, type ReactNode } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type {
  ActivityItem,
  Defect,
  Member,
  Paginated,
  Release,
  Requirement,
  TestCase,
  TraceLink,
} from "../api/types";
import { Avatar, Badge, Dialog, Drawer, EmptyState, Field, cap, errText, useToast } from "../ui";
import { Pager, SortHeader, sortBy, type SortState } from "../components/table";
import { Icons } from "../components/icons";

const PRIORITIES = ["critical", "high", "medium", "low"];
const REQ_TYPES = ["functional", "non_functional", "compliance", "ux", "performance", "security"];
const SOURCE_TYPES = ["manual", "import", "jira", "confluence", "email", "other"];
const STATUSES = ["draft", "active", "fulfilled", "archived"];
const NEXT_STATUS: Record<string, string[]> = {
  draft: ["active", "archived"],
  active: ["fulfilled", "archived"],
  fulfilled: ["active", "archived"],
  archived: ["draft"],
};
const PAGE = 20;
const COLUMN_KEYS = ["priority", "status", "coverage", "linked", "owner", "updated"] as const;
type ColumnKey = (typeof COLUMN_KEYS)[number];
const COLUMN_LABELS: Record<ColumnKey, string> = {
  priority: "Priority", status: "Status", coverage: "Test Coverage",
  linked: "Linked Tests", owner: "Owner", updated: "Updated",
};

function relDate(iso: string): string {
  const d = new Date(iso);
  const days = (Date.now() - d.getTime()) / 86_400_000;
  if (days < 1) return "Today";
  if (days < 2) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function coverageTone(pct: number): "" | "mid" | "low" {
  if (pct >= 70) return "";
  if (pct >= 40) return "mid";
  return "low";
}

function coveragePct(r: Requirement): number {
  if (!r.linked_test_count) return 0;
  return Math.round((r.qualifying_test_count / r.linked_test_count) * 100);
}

function useColumns() {
  const [cols, setCols] = useState<Set<ColumnKey>>(() => {
    try {
      const raw = localStorage.getItem("tq.req.columns");
      return raw ? new Set(JSON.parse(raw)) : new Set(COLUMN_KEYS);
    } catch {
      return new Set(COLUMN_KEYS);
    }
  });
  const toggle = (k: ColumnKey) =>
    setCols((prev) => {
      const next = new Set(prev);
      next.has(k) ? next.delete(k) : next.add(k);
      try { localStorage.setItem("tq.req.columns", JSON.stringify([...next])); } catch { /* ignore */ }
      return next;
    });
  return [cols, toggle] as const;
}

/* --------------------------------- CSV --------------------------------- */
function toCsv(rows: Requirement[]): string {
  const header = ["Key", "Title", "Priority", "Status", "Type", "Owner", "Release", "Linked Tests", "Test Coverage %", "Updated"];
  const esc = (v: unknown) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const lines = rows.map((r) =>
    [r.key, r.title, r.priority, r.status, r.req_type, r.owner_name ?? "", r.release_key ?? "", r.linked_test_count, coveragePct(r), r.updated_at]
      .map(esc)
      .join(","),
  );
  return [header.map(esc).join(","), ...lines].join("\n");
}

function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function parseCsv(text: string): Record<string, string>[] {
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) return [];
  const splitLine = (line: string): string[] => {
    const cells: string[] = [];
    let cur = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (inQuotes) {
        if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
        else if (c === '"') inQuotes = false;
        else cur += c;
      } else if (c === '"') inQuotes = true;
      else if (c === ",") { cells.push(cur); cur = ""; }
      else cur += c;
    }
    cells.push(cur);
    return cells;
  };
  const headers = splitLine(lines[0]).map((h) => h.trim().toLowerCase());
  return lines.slice(1).map((line) => {
    const cells = splitLine(line);
    const row: Record<string, string> = {};
    headers.forEach((h, i) => { row[h] = (cells[i] ?? "").trim(); });
    return row;
  });
}

/* ------------------------------ stat card ------------------------------ */
function StatCard({
  icon, label, value, tone, onClick, active,
}: { icon: ReactNode; label: string; value: number; tone?: "warn" | "info" | "purple"; onClick?: () => void; active?: boolean }) {
  const Comp = onClick ? "button" : "div";
  return (
    <Comp
      className={`kpi ${onClick ? "clickable" : "static"} ${tone ? `tone-${tone}` : ""} ${active ? "selected-row" : ""}`}
      onClick={onClick}
    >
      <span className="kpi-icon">{icon}</span>
      <div className="kpi-main">
        <span className="kpi-label">{label}</span>
        <div className="kpi-value">{value}</div>
      </div>
    </Comp>
  );
}

/* -------------------------------- page --------------------------------- */
export function RequirementsPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();

  const [search, setSearch] = useState("");
  const [release, setRelease] = useState("");
  const [priority, setPriority] = useState("");
  const [status, setStatus] = useState("active");
  const [reqType, setReqType] = useState("");
  const [coverageFilter, setCoverageFilter] = useState<"" | "covered" | "uncovered" | "changed">("");
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [view, setView] = useState<"list" | "grid">("list");
  const [columns, toggleColumn] = useColumns();
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sort, setSort] = useState<SortState>({ field: "key", dir: "asc" });
  const [page, setPage] = useState(1);

  const [dialog, setDialog] = useState<null | "new" | "edit" | "delete" | "import" | "assign" | "status" | "linkMany">(null);
  const [editReq, setEditReq] = useState<Requirement | null>(null);
  const [drawerReqId, setDrawerReqId] = useState<string | null>(null);
  const [drawerTab, setDrawerTab] = useState("Details");

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
  const defects = useQuery({
    queryKey: ["defects", pid],
    queryFn: () => http.get<Paginated<Defect>>(`/projects/${pid}/defects?page_size=200`),
    enabled: !!pid,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["reqs", pid] });
    qc.invalidateQueries({ queryKey: ["matrix"] });
  };

  const allRows = reqs.data?.items ?? [];
  // Everything except the stat-card toggle itself - the stat cards summarize
  // this set, so clicking one (e.g. "Uncovered") doesn't make its own count
  // collapse to zero or throw the other three cards off.
  const searchedAndFiltered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allRows.filter((r) => {
      if (q && !(r.title.toLowerCase().includes(q) || r.key.toLowerCase().includes(q) || (r.description ?? "").toLowerCase().includes(q))) return false;
      if (release && r.release_id !== release) return false;
      if (priority && r.priority !== priority) return false;
      if (status && r.status !== status) return false;
      if (reqType && r.req_type !== reqType) return false;
      return true;
    });
  }, [allRows, search, release, priority, status, reqType]);

  const filtered = useMemo(() => {
    if (!coverageFilter) return searchedAndFiltered;
    return searchedAndFiltered.filter((r) => {
      if (coverageFilter === "covered") return r.qualifying_test_count > 0;
      if (coverageFilter === "uncovered") return r.qualifying_test_count === 0;
      return r.version > 1; // changed
    });
  }, [searchedAndFiltered, coverageFilter]);

  const stats = useMemo(() => {
    const total = searchedAndFiltered.length;
    const covered = searchedAndFiltered.filter((r) => r.qualifying_test_count > 0).length;
    const changed = searchedAndFiltered.filter((r) => r.version > 1).length;
    return { total, covered, uncovered: total - covered, changed };
  }, [searchedAndFiltered]);

  const col = { key: (r: Requirement) => r.key, title: (r: Requirement) => r.title, priority: (r: Requirement) => r.priority, status: (r: Requirement) => r.status, owner_name: (r: Requirement) => r.owner_name ?? "", linked_test_count: (r: Requirement) => r.linked_test_count, updated_at: (r: Requirement) => r.updated_at, coverage: (r: Requirement) => coveragePct(r) };
  const getter = (col as Record<string, (r: Requirement) => unknown>)[sort.field] ?? col.key;
  const sorted = sortBy(filtered, getter, sort.dir);
  const pageRows = sorted.slice((page - 1) * PAGE, page * PAGE);
  const pages = Math.max(1, Math.ceil(sorted.length / PAGE));

  const drawerReq = drawerReqId ? allRows.find((r) => r.id === drawerReqId) ?? null : null;

  // deep-link from search / traceability: ?req=DEMO-REQ-1 opens that requirement
  const focusKey = params.get("req");
  useMemo(() => {
    if (!focusKey || !reqs.data) return;
    const found = reqs.data.items.find((r) => r.key === focusKey);
    if (found) { setDrawerReqId(found.id); setDrawerTab("Details"); }
    setParams((p) => { p.delete("req"); return p; }, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusKey, reqs.data]);

  const transition = useMutation({
    mutationFn: ({ id, version, to }: { id: string; version: number; to: string }) =>
      http.post(`/requirements/${id}/transitions`, { to, expected_version: version }),
    onSuccess: (_d, v) => { invalidate(); toast(`Status changed to ${cap(v.to)}`); },
    onError: (e) => toast(errText(e), "error"),
  });
  const removeReq = useMutation({
    mutationFn: (id: string) => http.del(`/requirements/${id}`),
    onSuccess: () => { invalidate(); setDialog(null); toast("Requirement deleted"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const clearSelection = () => setSelected(new Set());
  const toggleSelect = (id: string) =>
    setSelected((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const toggleSelectAll = () =>
    setSelected((prev) => (prev.size === pageRows.length ? new Set() : new Set(pageRows.map((r) => r.id))));

  const openDrawer = (r: Requirement) => { setDrawerReqId(r.id); setDrawerTab("Details"); };

  if (!project) return <p>Loading…</p>;

  const releaseChip = release && releases.data?.items.find((r) => r.id === release);

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Requirements</h2>
          <div className="page-sub">Manage product requirements and monitor test coverage</div>
        </div>
        <div className="inline-actions">
          <button onClick={() => setDialog("import")}>{Icons.upload} Import</button>
          <button onClick={() => downloadCsv(`${project.key}-requirements.csv`, toCsv(sorted))}>
            {Icons.download} Export
          </button>
          <button className="primary" onClick={() => setDialog("new")}>+ New Requirement</button>
        </div>
      </div>

      <div className="kpi-grid-4">
        <StatCard
          icon={Icons.requirements} label="Total Requirements" value={stats.total}
          active={coverageFilter === ""} onClick={() => setCoverageFilter("")}
        />
        <StatCard
          icon={Icons.checkCircle} label="Covered" value={stats.covered}
          active={coverageFilter === "covered"} onClick={() => setCoverageFilter((v) => (v === "covered" ? "" : "covered"))}
        />
        <StatCard
          icon={Icons.alertTriangle} label="Uncovered" tone="warn" value={stats.uncovered}
          active={coverageFilter === "uncovered"} onClick={() => setCoverageFilter((v) => (v === "uncovered" ? "" : "uncovered"))}
        />
        <StatCard
          icon={Icons.refresh} label="Changed" tone="purple" value={stats.changed}
          active={coverageFilter === "changed"} onClick={() => setCoverageFilter((v) => (v === "changed" ? "" : "changed"))}
        />
      </div>

      <div className="req-toolbar">
        <div className="req-search">
          {Icons.search}
          <input placeholder="Search requirements…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
        </div>
        {releaseChip && (
          <span className="filter-chip">
            Release: {releaseChip.key}
            <button onClick={() => setRelease("")} aria-label="Clear release filter">✕</button>
          </span>
        )}
        {!release && (
          <select className="filter-select" value={release} onChange={(e) => { setRelease(e.target.value); setPage(1); }}>
            <option value="">Release: All</option>
            {(releases.data?.items ?? []).map((r) => <option key={r.id} value={r.id}>{r.key} — {r.name}</option>)}
          </select>
        )}
        <select className="filter-select" value={priority} onChange={(e) => { setPriority(e.target.value); setPage(1); }}>
          <option value="">Priority: All</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{cap(p)}</option>)}
        </select>
        {status ? (
          <span className="filter-chip">
            Status: {cap(status)}
            <button onClick={() => setStatus("")} aria-label="Clear status filter">✕</button>
          </span>
        ) : (
          <select className="filter-select" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">Status: All</option>
            {STATUSES.map((s) => <option key={s} value={s}>{cap(s)}</option>)}
          </select>
        )}
        <button className={showMoreFilters ? "primary sm" : "sm"} onClick={() => setShowMoreFilters((v) => !v)}>
          {Icons.filter} More filters
        </button>
        <span className="spacer-flex" />
        <div className="view-toggle">
          <button className={view === "list" ? "active" : ""} onClick={() => setView("list")} aria-label="List view" aria-pressed={view === "list"}>
            {Icons.list}
          </button>
          <button className={view === "grid" ? "active" : ""} onClick={() => setView("grid")} aria-label="Grid view" aria-pressed={view === "grid"}>
            {Icons.grid}
          </button>
        </div>
      </div>

      {showMoreFilters && (
        <div className="field-row" style={{ marginBottom: 14 }}>
          <Field label="Type">
            <select value={reqType} onChange={(e) => { setReqType(e.target.value); setPage(1); }}>
              <option value="">All types</option>
              {REQ_TYPES.map((t) => <option key={t} value={t}>{cap(t)}</option>)}
            </select>
          </Field>
          <button className="sm ghost" style={{ alignSelf: "flex-end", marginBottom: 14 }}
            onClick={() => { setReqType(""); setPriority(""); setStatus(""); setRelease(""); setSearch(""); }}>
            Clear all filters
          </button>
        </div>
      )}

      {filtered.length === 0 ? (
        <EmptyState>No requirements match these filters.</EmptyState>
      ) : view === "grid" ? (
        <div className="req-cards">
          {pageRows.map((r) => (
            <div key={r.id} className="req-card" onClick={() => openDrawer(r)}>
              <div className="req-card-head">
                <span className="key-link">{r.key}</span>
                <Badge value={r.priority} />
              </div>
              <div className="req-card-title">{r.title}</div>
              <div className="coverage-cell">
                <div className="coverage-bar"><span className={`coverage-bar-fill ${coverageTone(coveragePct(r))}`} style={{ width: `${coveragePct(r)}%` }} /></div>
                <span className="coverage-pct">{coveragePct(r)}%</span>
              </div>
              <div className="req-card-foot">
                <div className="owner-cell"><Avatar name={r.owner_name} size={22} />{r.owner_name ?? <span className="muted">Unassigned</span>}</div>
                <Badge value={r.status} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="checkbox-cell">
                    <input type="checkbox" checked={pageRows.length > 0 && selected.size === pageRows.length} onChange={toggleSelectAll} aria-label="Select all" />
                  </th>
                  <SortHeader label="ID" field="key" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />
                  <SortHeader label="Requirement" field="title" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} />
                  {columns.has("priority") && <SortHeader label="Priority" field="priority" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />}
                  {columns.has("status") && <SortHeader label="Status" field="status" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />}
                  {columns.has("coverage") && <SortHeader label="Test Coverage" field="coverage" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} />}
                  {columns.has("linked") && <SortHeader label="Linked Tests" field="linked_test_count" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />}
                  {columns.has("owner") && <SortHeader label="Owner" field="owner_name" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />}
                  {columns.has("updated") && <SortHeader label="Updated" field="updated_at" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />}
                  <th className="nowrap" style={{ position: "relative" }}>
                    <button className="icon-btn" title="Manage columns" onClick={() => setColumnsOpen((v) => !v)}>{Icons.settings}</button>
                    {columnsOpen && (
                      <div className="app-menu-panel" style={{ position: "absolute", right: 0, top: "100%", zIndex: 10, padding: 10, minWidth: 180 }}>
                        {COLUMN_KEYS.map((k) => (
                          <label key={k} className="checkbox" style={{ display: "flex", padding: "5px 4px", fontWeight: 500, textTransform: "none" }}>
                            <input type="checkbox" checked={columns.has(k)} onChange={() => toggleColumn(k)} /> {COLUMN_LABELS[k]}
                          </label>
                        ))}
                      </div>
                    )}
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((r) => (
                  <tr key={r.id} className={`row-clickable ${selected.has(r.id) ? "selected-row" : ""}`}>
                    <td className="checkbox-cell" onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={selected.has(r.id)} onChange={() => toggleSelect(r.id)} aria-label={`Select ${r.key}`} />
                    </td>
                    <td className="key nowrap"><button className="key-link" onClick={() => openDrawer(r)}>{r.key}</button></td>
                    <td className="req-title" onClick={() => openDrawer(r)}>
                      {r.title}
                      {r.labels && <div className="muted small">{r.labels}</div>}
                    </td>
                    {columns.has("priority") && <td className="nowrap"><Badge value={r.priority} /></td>}
                    {columns.has("status") && <td className="nowrap"><Badge value={r.status} /></td>}
                    {columns.has("coverage") && (
                      <td>
                        <div className="coverage-cell">
                          <div className="coverage-bar"><span className={`coverage-bar-fill ${coverageTone(coveragePct(r))}`} style={{ width: `${coveragePct(r)}%` }} /></div>
                          <span className="coverage-pct">{coveragePct(r)}%</span>
                        </div>
                      </td>
                    )}
                    {columns.has("linked") && <td className="nowrap">{r.linked_test_count}</td>}
                    {columns.has("owner") && (
                      <td className="nowrap">
                        {r.owner_name ? <div className="owner-cell"><Avatar name={r.owner_name} size={22} />{r.owner_name}</div> : <span className="muted">—</span>}
                      </td>
                    )}
                    {columns.has("updated") && <td className="nowrap">{relDate(r.updated_at)}</td>}
                    <td className="nowrap">
                      <div className="inline-actions">
                        <button className="icon-btn" title="Edit" onClick={() => setEditReq(r)}>{Icons.edit}</button>
                        <button className="icon-btn warn" title="Delete" onClick={() => { setEditReq(r); setDialog("delete"); }}>{Icons.trash}</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pages={pages} total={sorted.length} pageSize={PAGE} onPage={setPage} />
        </>
      )}

      {selected.size > 0 && (
        <div className="bulk-bar">
          <span className="bulk-count">{selected.size} selected</span>
          <button className="sm" onClick={() => setDialog("assign")}>Assign</button>
          <button className="sm" onClick={() => setDialog("linkMany")}>Link Tests</button>
          <StatusMenu onPick={(to) => {
            const targets = [...selected].map((id) => allRows.find((r) => r.id === id)).filter((r): r is Requirement => !!r);
            Promise.all(targets.map((r) => transition.mutateAsync({ id: r.id, version: r.version, to }).catch(() => null)))
              .then(() => { toast(`Updated status for ${targets.length} requirement(s)`); clearSelection(); });
          }} />
          <button className="sm" onClick={() => downloadCsv("selected-requirements.csv", toCsv(allRows.filter((r) => selected.has(r.id))))}>
            {Icons.download} Export
          </button>
          <span className="spacer-flex" />
          <button className="icon-btn" onClick={clearSelection} aria-label="Clear selection">✕</button>
        </div>
      )}

      {(dialog === "new") && (
        <RequirementFormDialog
          projectId={pid!}
          releases={releases.data?.items ?? []}
          members={members.data ?? []}
          onClose={() => setDialog(null)}
          onDone={() => { invalidate(); setDialog(null); }}
        />
      )}
      {editReq && dialog !== "delete" && (
        <RequirementFormDialog
          req={editReq}
          projectId={pid!}
          releases={releases.data?.items ?? []}
          members={members.data ?? []}
          onClose={() => setEditReq(null)}
          onDone={() => { invalidate(); setEditReq(null); }}
        />
      )}
      {editReq && dialog === "delete" && (
        <Dialog title="Delete requirement" onClose={() => { setDialog(null); setEditReq(null); }}>
          <p>
            Delete <strong className="key">{editReq.key}</strong> — “{editReq.title}”? This removes it and
            its trace links permanently. This cannot be undone.
          </p>
          <div className="inline-actions" style={{ marginTop: 14 }}>
            <button className="danger" disabled={removeReq.isPending} onClick={() => removeReq.mutate(editReq.id)}>Delete</button>
            <button onClick={() => { setDialog(null); setEditReq(null); }}>Cancel</button>
          </div>
        </Dialog>
      )}
      {dialog === "import" && (
        <ImportDialog projectId={pid!} onClose={() => setDialog(null)} onDone={() => { invalidate(); setDialog(null); }} />
      )}
      {dialog === "assign" && (
        <AssignDialog
          members={members.data ?? []}
          onClose={() => setDialog(null)}
          onAssign={async (ownerId) => {
            const ids = [...selected];
            for (const id of ids) {
              const row = allRows.find((r) => r.id === id);
              if (!row) continue;
              await http.patch(`/requirements/${id}`, { expected_version: row.version, owner_id: ownerId || null, clear_owner: !ownerId }).catch(() => null);
            }
            invalidate();
            toast(`Assigned ${ids.length} requirement(s)`);
            clearSelection();
            setDialog(null);
          }}
        />
      )}
      {dialog === "linkMany" && (
        <LinkManyDialog
          testCases={cases.data?.items ?? []}
          onClose={() => setDialog(null)}
          onLink={async (tcId) => {
            const ids = [...selected];
            for (const id of ids) {
              await http.post(`/projects/${pid}/trace-links`, {
                source_type: "requirement", source_id: id, target_type: "test_case", target_id: tcId,
              }).catch(() => null);
            }
            invalidate();
            toast(`Linked test case to ${ids.length} requirement(s)`);
            clearSelection();
            setDialog(null);
          }}
        />
      )}

      {drawerReq && (
        <RequirementDrawer
          req={drawerReq}
          projectId={pid!}
          testCases={cases.data?.items ?? []}
          defects={defects.data?.items ?? []}
          activeTab={drawerTab}
          onTab={setDrawerTab}
          onClose={() => setDrawerReqId(null)}
          onChanged={invalidate}
        />
      )}
    </>
  );
}

function StatusMenu({ onPick }: { onPick: (to: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position: "relative" }}>
      <button className="sm" onClick={() => setOpen((v) => !v)}>{Icons.refresh} Change Status</button>
      {open && (
        <div className="app-menu-panel" style={{ position: "absolute", bottom: "100%", left: 0, marginBottom: 6, padding: 6, minWidth: 150, zIndex: 10 }}>
          {STATUSES.map((s) => (
            <button key={s} className="ghost sm" style={{ display: "block", width: "100%", textAlign: "left" }}
              onClick={() => { onPick(s); setOpen(false); }}>
              {cap(s)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------- drawer -------------------------------- */
function RequirementDrawer({
  req, projectId, testCases, defects, activeTab, onTab, onClose, onChanged,
}: {
  req: Requirement;
  projectId: string;
  testCases: TestCase[];
  defects: Defect[];
  activeTab: string;
  onTab: (t: string) => void;
  onClose: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const qc = useQueryClient();

  const links = useQuery({
    queryKey: ["req-links", req.id],
    queryFn: () => http.get<{ items: TraceLink[] }>(`/projects/${projectId}/trace-links?entity_type=requirement&entity_id=${req.id}`),
    enabled: activeTab === "Links",
  });
  const history = useQuery({
    queryKey: ["req-history", req.id],
    queryFn: () => http.get<{ items: ActivityItem[] }>(`/requirements/${req.id}/history`),
    enabled: activeTab === "History",
  });

  const removeLink = useMutation({
    mutationFn: (id: string) => http.del(`/trace-links/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["req-links", req.id] }); onChanged(); toast("Link removed"); },
    onError: (e) => toast(errText(e), "error"),
  });
  const [linkTc, setLinkTc] = useState("");
  const addLink = useMutation({
    mutationFn: () => http.post(`/projects/${projectId}/trace-links`, {
      source_type: "requirement", source_id: req.id, target_type: "test_case", target_id: linkTc,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["req-links", req.id] }); onChanged(); setLinkTc(""); toast("Linked"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const acItems = (req.acceptance_criteria ?? "").split(/\r?\n/).map((l) => l.replace(/^[-*•]\s*/, "").trim()).filter(Boolean);
  const summary = req.trace_summary ?? { test_cases: req.linked_test_count, executions: 0, defects: 0 };

  return (
    <Drawer
      title={req.key}
      subtitle={req.title}
      onClose={onClose}
      tabs={["Details", "Links", "History"]}
      activeTab={activeTab}
      onTab={onTab}
    >
      {activeTab === "Details" && (
        <>
          <div className="drawer-section">
            <h4>Description</h4>
            <p style={{ fontSize: 13, lineHeight: 1.6 }}>{req.description || <span className="muted">No description.</span>}</p>
          </div>
          <div className="drawer-section">
            <h4>Acceptance Criteria</h4>
            {acItems.length > 0 ? (
              <ul>{acItems.map((l, i) => <li key={i}>{l}</li>)}</ul>
            ) : (
              <p className="muted small">None recorded.</p>
            )}
          </div>
          <div className="drawer-section">
            <div className="drawer-kv"><span className="muted">Release</span><span>{req.release_key ? `${req.release_key} — ${req.release_name}` : <span className="muted">None</span>}</span></div>
            <div className="drawer-kv">
              <span className="muted">Owner</span>
              <span className="owner-cell">{req.owner_name ? <><Avatar name={req.owner_name} size={22} />{req.owner_name}</> : <span className="muted">Unassigned</span>}</span>
            </div>
            <div className="drawer-kv"><span className="muted">Priority</span><Badge value={req.priority} /></div>
            <div className="drawer-kv"><span className="muted">Status</span><Badge value={req.status} /></div>
          </div>
          <div className="drawer-section">
            <h4>Trace Summary</h4>
            <div className="trace-tiles">
              <div className="trace-tile">
                <span className="trace-tile-icon" style={{ background: "var(--info-bg)", color: "var(--info)" }}>{Icons.requirements}</span>
                <div className="trace-tile-value">{summary.test_cases}</div>
                <div className="trace-tile-label">Test Cases</div>
              </div>
              <div className="trace-tile">
                <span className="trace-tile-icon" style={{ background: "var(--success-bg)", color: "var(--success)" }}>{Icons.play}</span>
                <div className="trace-tile-value">{summary.executions}</div>
                <div className="trace-tile-label">Executions</div>
              </div>
              <div className="trace-tile">
                <span className="trace-tile-icon" style={{ background: "var(--danger-bg)", color: "var(--danger)" }}>{Icons.bug}</span>
                <div className="trace-tile-value">{summary.defects}</div>
                <div className="trace-tile-label">Defects</div>
              </div>
            </div>
          </div>
          <a className="btn primary" style={{ width: "100%", justifyContent: "center", display: "flex", gap: 6 }}
            href={`../traceability?req=${encodeURIComponent(req.key)}`}>
            Open Traceability {Icons.externalLink}
          </a>
        </>
      )}

      {activeTab === "Links" && (
        <div className="drawer-section">
          <h4>Linked test cases &amp; defects</h4>
          {links.isLoading && <p className="muted small">Loading…</p>}
          {(links.data?.items ?? []).map((l) => {
            const isSource = l.source_id === req.id;
            const otherType = isSource ? l.target_type : l.source_type;
            const otherId = isSource ? l.target_id : l.source_id;
            const other = otherType === "test_case" ? testCases.find((t) => t.id === otherId) : defects.find((d) => d.id === otherId);
            const label = other ? ("key" in other ? `${other.key} — ${"title" in other ? other.title : other.summary}` : otherId) : otherId;
            return (
              <div key={l.id} className="drawer-link-row">
                <span>{otherType === "test_case" ? Icons.repository : Icons.bug} {label}</span>
                <button className="icon-btn warn" title="Remove link" onClick={() => removeLink.mutate(l.id)}>{Icons.unlink}</button>
              </div>
            );
          })}
          {links.data && links.data.items.length === 0 && <p className="muted small">No links yet.</p>}
          <div className="field-row" style={{ marginTop: 12 }}>
            <Field label="Link a test case">
              <select value={linkTc} onChange={(e) => setLinkTc(e.target.value)}>
                <option value="">Select…</option>
                {testCases.map((t) => <option key={t.id} value={t.id}>{t.key} — {t.title}</option>)}
              </select>
            </Field>
            <button className="sm" style={{ alignSelf: "flex-end", marginBottom: 14 }} disabled={!linkTc || addLink.isPending} onClick={() => addLink.mutate()}>
              Link
            </button>
          </div>
        </div>
      )}

      {activeTab === "History" && (
        <div className="drawer-section">
          {history.isLoading && <p className="muted small">Loading…</p>}
          <div className="activity">
            {(history.data?.items ?? []).map((it) => (
              <div key={it.id} className="activity-item">
                <div className="activity-body">
                  <div>{it.text}</div>
                  <div className="muted small">{it.actor} · {new Date(it.at).toLocaleString()}</div>
                </div>
              </div>
            ))}
          </div>
          {history.data && history.data.items.length === 0 && <p className="muted small">No history yet.</p>}
        </div>
      )}
    </Drawer>
  );
}

/* ------------------------------ create/edit ------------------------------ */
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

  const statusOptions = editing ? [req!.status, ...(NEXT_STATUS[req!.status] ?? [])] : ["draft", "active"];

  const save = useMutation({
    mutationFn: () => {
      if (!editing) {
        return http.post(`/projects/${projectId}/requirements`, {
          title: f.title, description: f.description || null, acceptance_criteria: f.acceptance_criteria || null,
          priority: f.priority, status: f.status, req_type: f.req_type, owner_id: f.owner_id || null,
          component: f.component || null, labels: f.labels || null, source_type: f.source_type,
          external_reference: f.external_reference || null, release_id: f.release_id || null,
        });
      }
      return http.patch(`/requirements/${req!.id}`, {
        expected_version: req!.version, title: f.title, description: f.description,
        acceptance_criteria: f.acceptance_criteria, priority: f.priority, status: f.status, req_type: f.req_type,
        component: f.component, labels: f.labels, source_type: f.source_type, external_reference: f.external_reference,
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
      <Field label="Acceptance criteria" hint="One condition per line - shown as a checklist on the detail panel.">
        <textarea value={f.acceptance_criteria} onChange={set("acceptance_criteria")} rows={3} placeholder="Given / when / then, or a checklist of conditions" />
      </Field>
      <div className="field-row">
        <Field label="Priority">
          <select value={f.priority} onChange={set("priority")}>
            {PRIORITIES.map((p) => <option key={p} value={p}>{cap(p)}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select value={f.status} onChange={set("status")}>
            {statusOptions.map((s) => <option key={s} value={s}>{cap(s)}</option>)}
          </select>
        </Field>
        <Field label="Type">
          <select value={f.req_type} onChange={set("req_type")}>
            {REQ_TYPES.map((t) => <option key={t} value={t}>{cap(t)}</option>)}
          </select>
        </Field>
      </div>
      <div className="field-row">
        <Field label="Owner" hint="Only members of this project can be set as owner.">
          <select value={f.owner_id} onChange={set("owner_id")}>
            <option value="">— unassigned —</option>
            {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name}</option>)}
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
            {SOURCE_TYPES.map((s) => <option key={s} value={s}>{cap(s)}</option>)}
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
    </Dialog>
  );
}

/* -------------------------------- import -------------------------------- */
function ImportDialog({ projectId, onClose, onDone }: { projectId: string; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Record<string, string>[] | null>(null);

  const onFile = async (file: File) => {
    const text = await file.text();
    setPreview(parseCsv(text));
  };

  const run = async () => {
    if (!preview) return;
    setBusy(true);
    let ok = 0, failed = 0;
    for (const row of preview) {
      if (!row.title) { failed++; continue; }
      try {
        await http.post(`/projects/${projectId}/requirements`, {
          title: row.title,
          description: row.description || null,
          acceptance_criteria: row.acceptance_criteria || null,
          priority: PRIORITIES.includes(row.priority) ? row.priority : "medium",
          req_type: REQ_TYPES.includes(row.req_type) ? row.req_type : "functional",
          component: row.component || null,
          labels: row.labels || null,
          source_type: "import",
        });
        ok++;
      } catch { failed++; }
    }
    setBusy(false);
    toast(`Imported ${ok} requirement(s)${failed ? `, ${failed} skipped` : ""}`, failed && !ok ? "error" : "info");
    onDone();
  };

  return (
    <Dialog title="Import requirements" onClose={onClose}>
      <p className="muted small">
        CSV with a header row. Required column: <code>title</code>. Optional: <code>description</code>,{" "}
        <code>acceptance_criteria</code>, <code>priority</code>, <code>req_type</code>, <code>component</code>,{" "}
        <code>labels</code>.
      </p>
      <Field label="CSV file">
        <input ref={fileRef} type="file" accept=".csv,text/csv" onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} />
      </Field>
      {preview && <p className="muted small">{preview.length} row(s) ready to import.</p>}
      <div className="inline-actions" style={{ marginTop: 4 }}>
        <button className="primary" disabled={!preview || preview.length === 0 || busy} onClick={run}>
          {busy ? "Importing…" : `Import ${preview?.length ?? ""} requirement(s)`}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

/* ----------------------------- bulk dialogs ----------------------------- */
function AssignDialog({ members, onClose, onAssign }: { members: Member[]; onClose: () => void; onAssign: (ownerId: string) => Promise<void> }) {
  const [owner, setOwner] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog title="Assign owner" onClose={onClose}>
      <Field label="Owner">
        <select value={owner} onChange={(e) => setOwner(e.target.value)}>
          <option value="">— unassigned —</option>
          {members.map((m) => <option key={m.user_id} value={m.user_id}>{m.display_name}</option>)}
        </select>
      </Field>
      <div className="inline-actions" style={{ marginTop: 4 }}>
        <button className="primary" disabled={busy} onClick={async () => { setBusy(true); await onAssign(owner); setBusy(false); }}>
          {busy ? "Assigning…" : "Assign"}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}

function LinkManyDialog({ testCases, onClose, onLink }: { testCases: TestCase[]; onClose: () => void; onLink: (tcId: string) => Promise<void> }) {
  const [tc, setTc] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog title="Link test case to selected requirements" onClose={onClose}>
      <Field label="Test case">
        <select value={tc} onChange={(e) => setTc(e.target.value)}>
          <option value="">Select…</option>
          {testCases.map((t) => <option key={t.id} value={t.id}>{t.key} — {t.title}</option>)}
        </select>
      </Field>
      <div className="inline-actions" style={{ marginTop: 4 }}>
        <button className="primary" disabled={!tc || busy} onClick={async () => { setBusy(true); await onLink(tc); setBusy(false); }}>
          {busy ? "Linking…" : "Link"}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}
