import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { AuditLogRow, Paginated } from "../api/types";
import { Badge, EmptyState, cap } from "../ui";
import { Pager } from "../components/table";
import { Icons } from "../components/icons";

const ENTITY_TYPES = [
  "requirement", "test_case", "scenario", "plan", "cycle", "cycle_test", "attempt",
  "release", "defect", "trace_link", "folder", "project_membership", "feedback",
];
const PAGE_SIZE = 25;

function relTime(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  if (s < 604800) return `${Math.round(s / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function LogsPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;

  const [q, setQ] = useState("");
  const [entityType, setEntityType] = useState("");
  const [page, setPage] = useState(1);

  const log = useQuery({
    queryKey: ["audit-log", pid, q, entityType, page],
    queryFn: () =>
      http.get<Paginated<AuditLogRow>>(
        `/projects/${pid}/audit-log?` +
          new URLSearchParams({
            ...(q ? { q } : {}),
            ...(entityType ? { entity_type: entityType } : {}),
            page: String(page),
            page_size: String(PAGE_SIZE),
          }).toString(),
      ),
    enabled: !!pid,
  });

  if (!project) return <p>Loading…</p>;

  const rows = log.data?.items ?? [];

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Logs</h2>
          <div className="page-sub">Every user action recorded for this project - visible to project admins and test managers only</div>
        </div>
      </div>

      <div className="req-toolbar">
        <div className="req-search">
          {Icons.search}
          <input placeholder="Search action or key…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        </div>
        <select className="filter-select" value={entityType} onChange={(e) => { setEntityType(e.target.value); setPage(1); }}>
          <option value="">Type: All</option>
          {ENTITY_TYPES.map((t) => <option key={t} value={t}>{cap(t.replaceAll("_", " "))}</option>)}
        </select>
      </div>

      {log.isLoading ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <EmptyState>No activity matches these filters.</EmptyState>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th className="nowrap">Time</th>
                  <th className="nowrap">Actor</th>
                  <th>Action</th>
                  <th className="nowrap">Type</th>
                  <th className="nowrap">Key</th>
                  <th className="nowrap">Source</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="nowrap" title={new Date(r.at).toLocaleString()}>{relTime(r.at)}</td>
                    <td className="nowrap">{r.actor}</td>
                    <td>{r.text}</td>
                    <td className="nowrap"><Badge value={r.entity_type} /></td>
                    <td className="key nowrap">{r.entity_key ?? <span className="muted">—</span>}</td>
                    <td className="nowrap muted small">{r.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={log.data!.page} pages={log.data!.pages ?? 1} total={log.data!.total} pageSize={PAGE_SIZE} onPage={setPage} />
        </>
      )}
    </>
  );
}
