import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject, useList } from "../api/hooks";
import type { Cycle, ReportSummary } from "../api/types";
import { Card, EmptyState } from "../ui";
import { useState } from "react";

function metricAccent(id: string): string {
  if (["M-01", "M-02", "M-03", "M-04"].includes(id)) return "var(--sec-repository)"; // execution
  if (["M-05", "M-06", "M-07", "M-08", "M-09"].includes(id)) return "var(--sec-plans)"; // coverage
  if (["M-10", "M-11"].includes(id)) return "var(--sec-traceability)"; // defects
  return "var(--sec-backlog)"; // automation / trace links
}

export function DashboardPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const [cycleId, setCycleId] = useState("");

  const cycles = useList<Cycle[]>(["cycles", pid], `/projects/${pid}/cycles`, !!pid);
  const query = new URLSearchParams(cycleId ? { cycle_id: cycleId } : {}).toString();
  const summary = useQuery({
    queryKey: ["summary", pid, cycleId],
    queryFn: () => http.get<ReportSummary>(`/projects/${pid}/reports/summary?${query}`),
    enabled: !!pid,
  });

  if (!project) return <p>Loading project…</p>;

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <div className="inline-actions">
          <select value={cycleId} onChange={(e) => setCycleId(e.target.value)} style={{ width: "auto" }}>
            <option value="">All cycles (project scope)</option>
            {cycles.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.key} · {c.name} ({c.environment}/{c.build})
              </option>
            ))}
          </select>
          {pid && (
            <a
              className="btn"
              href={`${import.meta.env.VITE_API_BASE ?? "/api/v1"}/projects/${pid}/reports/summary.csv?${query}`}
            >
              Export CSV
            </a>
          )}
        </div>
      </div>

      {summary.isLoading && <p>Computing metrics…</p>}
      {summary.data && (
        <>
          <p className="stale">
            Data as of {new Date(summary.data.data_as_of).toLocaleString()} · formula v
            {summary.data.formula_version}
          </p>
          <div className="grid cols-3">
            {summary.data.metrics.map((m) => (
              <Card
                key={m.metric_id}
                className="metric"
                style={{ ["--metric-accent" as string]: metricAccent(m.metric_id) }}
              >
                <div className="value">{m.display}</div>
                <div className="label">
                  {m.metric_id} · {m.label}
                </div>
                <div className="sub">
                  {m.kind === "ratio" && m.denominator !== null
                    ? `${m.numerator} / ${m.denominator}`
                    : m.denominator === null && m.kind === "ratio"
                      ? "no data in scope"
                      : ""}
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
      {summary.data && summary.data.metrics.length === 0 && (
        <EmptyState>No metric data for this scope.</EmptyState>
      )}
    </>
  );
}
