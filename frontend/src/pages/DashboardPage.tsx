import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { http } from "../api/client";
import { useProject, useList } from "../api/hooks";
import type {
  Cycle,
  CycleBreakdownRow,
  Metric,
  Paginated,
  Release,
  ReleaseOverviewRow,
  ReportSummary,
} from "../api/types";
import { Badge, Card, EmptyState } from "../ui";
import { DrillDownDialog } from "../components/DrillDownDialog";

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

const COVERAGE = ["M-05", "M-06", "M-07", "M-08", "M-09"];
const EXECUTION = ["M-01", "M-02", "M-03", "M-04"];
const QUALITY = ["M-10", "M-11", "M-12", "M-13"];

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

function Headline({ m, onOpen, invert = false }: { m: Metric; onOpen: () => void; invert?: boolean }) {
  const meta = META[m.metric_id];
  const good = m.kind === "count" ? (invert ? m.value === 0 : true) : (m.value ?? 0) >= 0.8;
  return (
    <button
      className="card headline"
      title={`${meta.help}\nClick to see the records`}
      onClick={onOpen}
    >
      <div className="headline-value" style={{ color: invert && m.value ? "var(--danger)" : undefined }}>
        {m.display}
      </div>
      <div className="headline-name">
        {meta.name} <span className="drill-hint">↗</span>
      </div>
      {m.kind === "ratio" && (
        <>
          <Bar value={m.value} accent={good ? "var(--success)" : meta.accent} />
          <div className="headline-sub">
            {m.denominator !== null ? `${m.numerator} of ${m.denominator}` : "no data in scope"}
          </div>
        </>
      )}
    </button>
  );
}

function pct(v: number | null): string {
  return v === null ? "–" : `${(v * 100).toFixed(1)}%`;
}

function CycleBreakdown({
  rows,
  onOpenCycle,
}: {
  rows: CycleBreakdownRow[];
  onOpenCycle: (cycleId: string) => void;
}) {
  if (rows.length === 0) {
    return <p className="muted">No cycles in scope yet. Create a plan and a cycle to track execution.</p>;
  }
  return (
    <div className="cycle-breakdown">
      {rows.map((c) => (
        <button key={c.cycle_id} className="cycle-row" onClick={() => onOpenCycle(c.cycle_id)} title="Open in Cycles">
          <div className="cycle-row-head">
            <span className="key">{c.cycle_key}</span>
            <span className="cycle-name">{c.name}</span>
            <span className="muted">{c.environment} / {c.build}</span>
            <Badge value={c.status} />
            <span className="drill-hint" style={{ marginLeft: "auto" }}>↗</span>
          </div>
          <div className="cycle-row-metrics">
            <div>
              <div className="cm-label">Completion</div>
              <Bar value={c.completion} accent="var(--sec-repository)" />
              <div className="cm-value">{pct(c.completion)} · {c.terminal}/{c.scoped}</div>
            </div>
            <div>
              <div className="cm-label">Pass rate</div>
              <Bar value={c.pass_rate} accent={(c.pass_rate ?? 0) >= 0.8 ? "var(--success)" : "var(--sec-cycles)"} />
              <div className="cm-value">{pct(c.pass_rate)}</div>
            </div>
            <div className="cm-counts">
              <span className="badge PASSED">{c.passed} passed</span>
              <span className="badge FAILED">{c.failed} failed</span>
              <span className="badge BLOCKED">{c.blocked} blocked</span>
              <span className="badge NOT_RUN">{c.not_run} not run</span>
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}

function ReleaseRollup({
  rows,
  activeReleaseId,
  onPickRelease,
  onOpenCycles,
}: {
  rows: ReleaseOverviewRow[];
  activeReleaseId: string;
  onPickRelease: (id: string) => void;
  onOpenCycles: () => void;
}) {
  if (rows.length === 0) {
    return <p className="muted">No releases yet. Create one in the Releases tab to track release-wise execution.</p>;
  }
  return (
    <div className="stack">
      {rows.map((r) => (
        <div key={r.release_id} className={`release-rollup ${activeReleaseId === r.release_id ? "on" : ""}`}>
          <button className="release-head" onClick={() => onPickRelease(activeReleaseId === r.release_id ? "" : r.release_id)}>
            <span className="key">{r.release_key}</span>
            <span className="release-name">{r.name}</span>
            {r.version_label && <span className="mtag">{r.version_label}</span>}
            <Badge value={r.status} />
            <span className="muted">{r.cycle_count} cycles · {r.requirements} requirements</span>
            {r.open_critical_defects > 0 && (
              <span className="badge FAILED">{r.open_critical_defects} open critical</span>
            )}
            <span className="drill-hint" style={{ marginLeft: "auto" }}>
              {activeReleaseId === r.release_id ? "scoped ✓" : "scope to this"}
            </span>
          </button>
          <div className="cycle-row-metrics" style={{ marginTop: 8 }}>
            <div>
              <div className="cm-label">Completion</div>
              <Bar value={r.completion} accent="var(--sec-repository)" />
              <div className="cm-value">{pct(r.completion)} · {r.terminal}/{r.scoped_tests}</div>
            </div>
            <div>
              <div className="cm-label">Pass rate</div>
              <Bar value={r.pass_rate} accent={(r.pass_rate ?? 0) >= 0.8 ? "var(--success)" : "var(--sec-cycles)"} />
              <div className="cm-value">{pct(r.pass_rate)}</div>
            </div>
            <div className="cm-counts">
              {r.cycles.slice(0, 6).map((c) => (
                <button key={c.cycle_id} className="badge" onClick={onOpenCycles} title={`${c.name} — ${pct(c.completion)} complete`}>
                  {c.cycle_key} {pct(c.completion)}
                </button>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function MetricRow({ m, onOpen }: { m: Metric; onOpen: () => void }) {
  const meta = META[m.metric_id];
  return (
    <button className="metric-row" title={`${meta.help}\nClick to see the records`} onClick={onOpen}>
      <div className="metric-row-label">
        {meta.name}
        <span className="mtag">{m.metric_id}</span>
        <span className="drill-hint">↗</span>
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
    </button>
  );
}

export function DashboardPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const nav = useNavigate();
  const [releaseId, setReleaseId] = useState("");
  const [cycleId, setCycleId] = useState("");
  const [openMetric, setOpenMetric] = useState<string | null>(null);

  const releases = useList<Paginated<Release>>(
    ["releases", pid],
    `/projects/${pid}/releases?page_size=200`,
    !!pid,
  );
  const cycles = useList<Cycle[]>(
    ["cycles", pid, releaseId],
    `/projects/${pid}/cycles${releaseId ? `?release_id=${releaseId}` : ""}`,
    !!pid,
  );
  const releaseOverview = useList<{ releases: ReleaseOverviewRow[] }>(
    ["release-overview", pid],
    `/projects/${pid}/reports/release-overview`,
    !!pid,
  );

  const scopeParams: Record<string, string> = {};
  if (releaseId) scopeParams.release_id = releaseId;
  if (cycleId) scopeParams.cycle_id = cycleId;
  const query = new URLSearchParams(scopeParams).toString();

  const summary = useQuery({
    queryKey: ["summary", pid, releaseId, cycleId],
    queryFn: () => http.get<ReportSummary>(`/projects/${pid}/reports/summary?${query}`),
    enabled: !!pid,
  });
  const breakdown = useQuery({
    queryKey: ["cycle-breakdown", pid, releaseId, cycleId],
    queryFn: () =>
      http.get<{ cycles: CycleBreakdownRow[] }>(`/projects/${pid}/reports/cycle-breakdown?${query}`),
    enabled: !!pid,
  });

  if (!project) return <p>Loading project…</p>;
  const byId = Object.fromEntries((summary.data?.metrics ?? []).map((m) => [m.metric_id, m]));
  const relRows = releaseOverview.data?.releases ?? [];

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <div className="inline-actions">
          <select
            value={releaseId}
            onChange={(e) => { setReleaseId(e.target.value); setCycleId(""); }}
            style={{ width: "auto" }}
            aria-label="Release scope"
          >
            <option value="">All releases</option>
            {releases.data?.items.map((r) => (
              <option key={r.id} value={r.id}>Release: {r.key} · {r.name}</option>
            ))}
          </select>
          <select value={cycleId} onChange={(e) => setCycleId(e.target.value)} style={{ width: "auto" }} aria-label="Cycle scope">
            <option value="">{releaseId ? "All cycles in release" : "All cycles"}</option>
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
            {byId["M-05"] && <Headline m={byId["M-05"]} onOpen={() => setOpenMetric("M-05")} />}
            {byId["M-02"] && <Headline m={byId["M-02"]} onOpen={() => setOpenMetric("M-02")} />}
            {byId["M-03"] && <Headline m={byId["M-03"]} onOpen={() => setOpenMetric("M-03")} />}
            {byId["M-10"] && <Headline m={byId["M-10"]} onOpen={() => setOpenMetric("M-10")} invert />}
          </div>

          <Card>
            <h3 className="section-title" style={{ ["--dot" as string]: "var(--sec-releases)" }}>
              Releases
            </h3>
            <ReleaseRollup
              rows={relRows}
              activeReleaseId={releaseId}
              onPickRelease={(id) => { setReleaseId(id); setCycleId(""); }}
              onOpenCycles={() => nav(`/p/${projectKey}/cycles`)}
            />
          </Card>

          <Card>
            <h3 className="section-title" style={{ ["--dot" as string]: META["M-05"].accent }}>
              Requirement coverage
            </h3>
            <div className="metric-list">
              {COVERAGE.filter((id) => byId[id]).map((id) => (
                <MetricRow key={id} m={byId[id]} onOpen={() => setOpenMetric(id)} />
              ))}
            </div>
          </Card>

          <Card>
            <h3 className="section-title" style={{ ["--dot" as string]: META["M-02"].accent }}>
              Execution progress by cycle
            </h3>
            <CycleBreakdown
              rows={breakdown.data?.cycles ?? []}
              onOpenCycle={() => nav(`/p/${projectKey}/cycles`)}
            />
            {(breakdown.data?.cycles.length ?? 0) > 0 && (
              <>
                <div className="metric-sub-title">Across all cycles in scope</div>
                <div className="metric-list">
                  {EXECUTION.filter((id) => byId[id]).map((id) => (
                    <MetricRow key={id} m={byId[id]} onOpen={() => setOpenMetric(id)} />
                  ))}
                </div>
              </>
            )}
          </Card>

          <Card>
            <h3 className="section-title" style={{ ["--dot" as string]: META["M-10"].accent }}>
              Quality signals
            </h3>
            <div className="metric-list">
              {QUALITY.filter((id) => byId[id]).map((id) => (
                <MetricRow key={id} m={byId[id]} onOpen={() => setOpenMetric(id)} />
              ))}
            </div>
          </Card>

          {summary.data.metrics.length === 0 && (
            <EmptyState>
              No metric data yet. Add requirements, link tests, then run a cycle to see coverage and pass rates here.
            </EmptyState>
          )}
        </div>
      )}

      {openMetric && pid && projectKey && (
        <DrillDownDialog
          projectId={pid}
          projectKey={projectKey}
          metricId={openMetric}
          query={query}
          onClose={() => setOpenMetric(null)}
        />
      )}
    </>
  );
}
