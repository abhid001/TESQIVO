import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { http } from "../api/client";
import { Badge, Dialog, EmptyState } from "../ui";
import { Pager, SortHeader, sortBy, type SortState } from "./table";

const PAGE_SIZE = 15;

interface DrillRow {
  cells: Record<string, string>;
  link: { kind: string; id: string; key: string } | null;
}
interface DrillDown {
  metric_id: string;
  label: string;
  help: string;
  columns: { key: string; label: string }[];
  rows: DrillRow[];
  row_count: number;
}

const NARROW = new Set([
  "result", "env", "cycle", "severity", "status", "resolvable", "type", "automation",
]);
const STATUSY = new Set([
  "PASSED", "FAILED", "BLOCKED", "SKIPPED", "ABORTED", "NOT_RUN", "IN_PROGRESS", "RETEST_PENDING",
  "counted", "not counted", "yes", "no",
  "draft", "active", "in_review", "approved", "deprecated", "archived",
  "new", "open", "in_progress", "resolved", "closed", "rejected",
  "critical", "high", "major", "minor", "trivial",
  "automated", "candidate", "not_applicable",
]);

export function DrillDownDialog({
  projectId,
  projectKey,
  metricId,
  query,
  onClose,
}: {
  projectId: string;
  projectKey: string;
  metricId: string;
  query: string;
  onClose: () => void;
}) {
  const nav = useNavigate();
  const [sort, setSort] = useState<SortState | null>(null);
  const [page, setPage] = useState(1);

  const q = useQuery({
    queryKey: ["drilldown", projectId, metricId, query],
    queryFn: () =>
      http.get<DrillDown>(`/projects/${projectId}/reports/${metricId}/drill-down?${query}`),
  });

  const goto = (link: DrillRow["link"]) => {
    if (!link) return;
    if (link.kind === "test_case") {
      onClose();
      nav(`/p/${projectKey}/repository/${link.id}`);
    }
  };

  const rows = q.data?.rows ?? [];
  const sorted = useMemo(() => {
    if (!sort) return rows;
    return sortBy(rows, (r) => r.cells[sort.field] ?? "", sort.dir);
  }, [rows, sort]);
  const pageRows = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const pages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));

  return (
    <Dialog title={q.data ? `${metricId} · ${q.data.label}` : `${metricId} · drill-down`} onClose={onClose}>
      {q.isLoading && <p>Loading records…</p>}
      {q.data && (
        <>
          <p className="muted" style={{ marginTop: 0 }}>{q.data.help}</p>
          <p className="muted" style={{ fontSize: 12.5 }}>{q.data.row_count} record(s)</p>
          {rows.length === 0 ? (
            <EmptyState>No contributing records for this scope.</EmptyState>
          ) : (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {q.data.columns.map((c) => (
                        <SortHeader
                          key={c.key}
                          label={c.label}
                          field={c.key}
                          sort={sort}
                          onSort={(s) => { setSort(s); setPage(1); }}
                        />
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((r, i) => (
                      <tr
                        key={i}
                        onClick={() => goto(r.link)}
                        className={r.link ? "drill-linked" : undefined}
                        title={r.link ? "Open record" : undefined}
                      >
                        {q.data!.columns.map((c) => {
                          const v = r.cells[c.key] ?? "";
                          return (
                            <td key={c.key} className={NARROW.has(c.key) ? "nowrap" : "drill-wide"}>
                              {STATUSY.has(v) ? <Badge value={v} /> : v}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pager page={page} pages={pages} total={sorted.length} pageSize={PAGE_SIZE} onPage={setPage} />
            </>
          )}
        </>
      )}
    </Dialog>
  );
}
