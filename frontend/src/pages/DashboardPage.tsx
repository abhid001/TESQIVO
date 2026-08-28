import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { http } from "../api/client";
import { useProject, useList } from "../api/hooks";
import type { Cycle, Metric, ReportSummary } from "../api/types";
import { Card, EmptyState } from "../ui";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

/** Plain-language names + one-line explanations, keyed by metric id. */
const META: Record<string, { name: string; help: string; accent: string }> = {
  "M-01": { name: "Tests in scope", help: "Distinct cycle tests in the selected scope.", accent: "var(--sec-repository)" },
  "M-02": { name: "Execution complete", help: "Cycle tests with a finished result (passed, failed, blocked, skipped or aborted).", accent: "var(--sec-repository)" },
  "M-03": { name: "Pass rate", help: "Passed ÷ (passed + failed + blocked). Skipped and not-run are excluded.", accent: "var(--sec-repository)" },
  "M-04": { name: "Not started", help: "Cycle tests with no attempt yet.", accent: "var(--sec-repository)" },
  "M-05": { name: "Design coverage", help: "Active requirements with at least one approved/active linked test.", accent: "var(--sec-plans)" },
  "M-06": { name: "Plan coverage", help: "Active requirements covered by a test that is in the selected plan/cycle scope.", accent: "var(--sec-plans)" },
  "M-07": { name: "Execution coverage", help: "Active requirements whose linked in-scope test has been executed.", accent: "var(--sec-plans)" },
  "M-08": { name: "Pass coverage", help: "Active requirements for which every qualifying in-scope test passed.", accent: "var(--sec-plans)" },
  "M-09": { name: "Uncovered requirements", help: "Active requirements with no qualifying linked test.", accent: "var(--sec-plans)" },
  "M-10": { name: "Open critical defects", help: "Distinct critical defects that are not closed or rejected.", accent: "var(--sec-traceability)" },
  "M-11": { name: "Requirements at risk", help: "Active requirements linked to an open/in-progress critical or high defect.", accent: "var(--sec-traceability)" },
  "M-12": { name: "Automation coverage", help: "Automated ÷ automation-eligible active tests.", accent: "var(--sec-backlog)" },
  "M-13": { name: "Trace-link health", help: "Resolvable ÷ total active trace links.", accent: "var(--sec-backlog)" },
};

const GROUPS: { title: string; ids: string[] }[] = [
  { title: "Requirement coverage", ids: ["M-05", "M-06", "M-07", "M-08", "M-09"] },
  { title: "Execution progress", ids: ["M-01", "M-02", "M-03", "M-04"] },
  { title: "Quality signals", ids: ["M-10", "M-11", "M-12", "M-13"] },
];

function relTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "moments ago";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  return new Date(iso).toLocaleString();
}

function Bar({ value, accent }: { value: number | null; accent: string }) {
  if (value === null) return <div className="mbar" aria-hidden />;
  return (
    <div className="mbar">
      <span style={{ width: `${Math.round(value * 100)}%`, background: accent }} />
    </div>
  );
}

function Headline({ m, invert = false }: { m: Metric; invert?: boolean }) {
  const meta = META[m.metric_id];
  const good = m.kind === "count" ? (invert ? m.value === 0 : true) : (m.value ?? 0) >= 0.8;
  return (
    <Card className="headline" title={meta.help}>
      <div className="headline-value" style={{ color: invert && m.value ? "var(--danger)" : undefined }}>
        {m.display}
      </div>
      <div className="headline-name">{meta.name}</div>
      {m.kind === "ratio" && (
        <>
          <Bar value={m.value} accent={good ? "var(--success)" : meta.accent} />
          <div className="headline-sub">
            {m.denominator !== null ? `${m.numerator} of ${m.denominator}` : "no data in scope"}
          </div>
        </>
      )}
    </Card>
  );
}

function MetricRow({ m }: { m: Metric }) {
  const meta = META[m.metric_id];
  return (
    <div className="metric-row" title={meta.help}>
      <div className="metric-row-label">
        {meta.name}
        <span className="mtag">{m.metric_id}</span>
      </div>
      {m.kind === "ratio" ? (
        <>
          <Bar value={m.value} accent={meta.accent} />
          <div className="metric-row-value">
            {m.display}
            <span className="muted">
              {m.denominator !== null ? ` · ${m.numerator}/${m.denominator}` : ""}
            </span>
          </div>
        </>
      ) : (
        <>
          <div />
          <div className="metric-row-value">{m.display}</div>
        </>
      )}
    </div>
  );
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
  const byId = Object.fromEntries((summary.data?.metrics ?? []).map((m) => [m.metric_id, m]));

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <div className="inline-actions">
          <select value={cycleId} onChange={(e) => setCycleId(e.target.value)} style={{ width: "auto" }}>
            <option value="">Whole project</option>
            {cycles.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.key} · {c.name} ({c.environment}/{c.build})
              </option>
            ))}
          </select>
          {pid && (
            <a className="btn" href={`${API_BASE}/projects/${pid}/reports/summary.csv?${query}`}>
              Export CSV
            </a>
          )}
        </div>
      </div>

      {summary.isLoading && <p>Computing metrics…</p>}

      {summary.data && (
        <div className="stack">
          <p className="muted" style={{ fontSize: 12.5 }} title={`formula v${summary.data.formula_version}`}>
            Updated {relTime(summary.data.data_as_of)} · every number links to its underlying records
          </p>

          <div className="headline-grid">
            {byId["M-05"] && <Headline m={byId["M-05"]} />}
            {byId["M-02"] && <Headline m={byId["M-02"]} />}
            {byId["M-03"] && <Headline m={byId["M-03"]} />}
            {byId["M-10"] && <Headline m={byId["M-10"]} invert />}
          </div>

          {GROUPS.map((g) => (
            <Card key={g.title}>
              <h3 className="section-title" style={{ ["--dot" as string]: META[g.ids[0]].accent }}>
                {g.title}
              </h3>
              <div className="metric-list">
                {g.ids.filter((id) => byId[id]).map((id) => (
                  <MetricRow key={id} m={byId[id]} />
                ))}
              </div>
            </Card>
          ))}

          {summary.data.metrics.length === 0 && (
            <EmptyState>
              No metric data yet. Add requirements, link tests, then run a cycle to see coverage and pass rates here.
            </EmptyState>
          )}
        </div>
      )}
    </>
  );
}
