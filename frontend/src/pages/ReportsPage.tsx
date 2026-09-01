import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject, useList } from "../api/hooks";
import type { Cycle, Metric, Paginated, Release, ReportSummary } from "../api/types";
import { Card, EmptyState } from "../ui";
import { DrillDownDialog } from "../components/DrillDownDialog";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

const GROUPS: { title: string; ids: string[] }[] = [
  { title: "Execution", ids: ["M-01", "M-02", "M-03", "M-04"] },
  { title: "Requirement coverage", ids: ["M-05", "M-06", "M-07", "M-08", "M-09"] },
  { title: "Quality & traceability", ids: ["M-10", "M-11", "M-12", "M-13"] },
];

export function ReportsPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const [releaseId, setReleaseId] = useState("");
  const [cycleId, setCycleId] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const releases = useList<Paginated<Release>>(["releases", pid], `/projects/${pid}/releases?page_size=200`, !!pid);
  const cycles = useList<Cycle[]>(
    ["cycles", pid, releaseId],
    `/projects/${pid}/cycles${releaseId ? `?release_id=${releaseId}` : ""}`,
    !!pid,
  );

  const params: Record<string, string> = {};
  if (releaseId) params.release_id = releaseId;
  if (cycleId) params.cycle_id = cycleId;
  const query = new URLSearchParams(params).toString();

  const summary = useQuery({
    queryKey: ["summary", pid, releaseId, cycleId],
    queryFn: () => http.get<ReportSummary>(`/projects/${pid}/reports/summary?${query}`),
    enabled: !!pid,
  });

  if (!project) return <p>Loading…</p>;
  const byId: Record<string, Metric> = Object.fromEntries((summary.data?.metrics ?? []).map((m) => [m.metric_id, m]));

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Reports</h2>
          <div className="page-sub">Every Phase-1 metric, with the records behind each number</div>
        </div>
        <div className="inline-actions">
          <select value={releaseId} onChange={(e) => { setReleaseId(e.target.value); setCycleId(""); }} style={{ width: "auto" }} aria-label="Release scope">
            <option value="">All releases</option>
            {releases.data?.items.map((r) => <option key={r.id} value={r.id}>Release: {r.version_label || r.key}</option>)}
          </select>
          <select value={cycleId} onChange={(e) => setCycleId(e.target.value)} style={{ width: "auto" }} aria-label="Cycle scope">
            <option value="">{releaseId ? "All cycles in release" : "All cycles"}</option>
            {cycles.data?.map((c) => <option key={c.id} value={c.id}>{c.key} · {c.name}</option>)}
          </select>
          {pid && <a className="btn primary" href={`${API_BASE}/projects/${pid}/reports/summary.csv?${query}`}>Export CSV</a>}
        </div>
      </div>

      {summary.isLoading && <p>Computing…</p>}
      {summary.data && summary.data.metrics.length === 0 && (
        <EmptyState>No metric data yet.</EmptyState>
      )}

      {summary.data && summary.data.metrics.length > 0 && (
        <div className="stack">
          {GROUPS.map((g) => (
            <Card key={g.title}>
              <div className="card-title">{g.title}</div>
              <div className="table-wrap" style={{ border: "none", boxShadow: "none" }}>
                <table>
                  <thead>
                    <tr><th>Metric</th><th className="nowrap">Value</th><th className="nowrap">Numerator</th><th className="nowrap">Denominator</th><th></th></tr>
                  </thead>
                  <tbody>
                    {g.ids.filter((id) => byId[id]).map((id) => {
                      const m = byId[id];
                      return (
                        <tr key={id}>
                          <td><strong>{m.label}</strong></td>
                          <td className="nowrap"><strong>{m.display}</strong></td>
                          <td className="nowrap">{m.numerator ?? "–"}</td>
                          <td className="nowrap">{m.denominator ?? "–"}</td>
                          <td className="nowrap"><button className="sm" onClick={() => setOpen(id)}>View records ↗</button></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          ))}
          <p className="muted small">Formula version {summary.data.formula_version} · computed {new Date(summary.data.data_as_of).toLocaleString()}</p>
        </div>
      )}

      {open && pid && projectKey && (
        <DrillDownDialog projectId={pid} projectKey={projectKey} metricId={open} query={query} onClose={() => setOpen(null)} />
      )}
    </>
  );
}
