import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { http } from "../api/client";
import { useProject, useProjects, useList } from "../api/hooks";
import type {
  ActivityItem,
  CoverageByType,
  Cycle,
  CycleBreakdownRow,
  Defect,
  MatrixRow,
  Metric,
  Paginated,
  ReferenceValue,
  Release,
  ReleaseOverviewRow,
  ReportSummary,
  Requirement,
  TestCase,
  TrendPoint,
} from "../api/types";
import { Badge, Card, EmptyState } from "../ui";
import { Icons } from "../components/icons";
import { DrillDownDialog } from "../components/DrillDownDialog";
import { Donut, Gauge, HBars, TrendChart } from "../components/Charts";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

const META: Record<string, { name: string; help: string }> = {
  "M-02": { name: "Execution complete", help: "Cycle tests with a finished result." },
  "M-03": { name: "Pass rate", help: "Passed ÷ (passed + failed + blocked)." },
  "M-05": { name: "Design coverage", help: "Active requirements with an approved linked test." },
  "M-06": { name: "Plan coverage", help: "Active requirements covered by an in-scope test." },
  "M-07": { name: "Execution coverage", help: "Active requirements whose in-scope test ran." },
  "M-08": { name: "Pass coverage", help: "Active requirements where every qualifying test passed." },
  "M-09": { name: "Uncovered requirements", help: "Active requirements with no qualifying linked test." },
  "M-10": { name: "Open critical defects", help: "Critical defects not closed or rejected." },
  "M-11": { name: "Requirements at risk", help: "Active requirements linked to an open critical/high defect." },
  "M-12": { name: "Automation coverage", help: "Automated ÷ automation-eligible active tests." },
  "M-13": { name: "Trace-link health", help: "Resolvable ÷ total active trace links." },
};

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "–" : `${(v * 100).toFixed(0)}%`;
}
function pct1(v: number | null | undefined): string {
  return v === null || v === undefined ? "–" : `${(v * 100).toFixed(1)}%`;
}
function relTime(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  if (s < 604800) return `${Math.round(s / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

const ActIcon: Record<string, ReactNode> = {
  ok: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>,
  bad: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>,
  info: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><circle cx="12" cy="12" r="9" /><path d="M12 8h.01M11 12h1v4h1" /></svg>,
};

function FixedCard({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <Card>
      <div className="card-title">{title}{action}</div>
      <div className="card-body">{children}</div>
    </Card>
  );
}

function RecentActivity({ items }: { items: ActivityItem[] }) {
  const [all, setAll] = useState(false);
  if (items.length === 0) return <p className="muted">No activity yet.</p>;
  const shown = all ? items : items.slice(0, 4);
  return (
    <>
      <div className="activity">
        {shown.map((a) => (
          <div key={a.id} className="activity-item">
            <span className={`activity-ic ${a.kind}`}>{ActIcon[a.kind]}</span>
            <div className="activity-body">
              <div>{a.text}</div>
              <div className="muted small">{a.actor}</div>
            </div>
            <span className="activity-time">{relTime(a.at)}</span>
          </div>
        ))}
      </div>
      {items.length > 4 && (
        <button className="btn sm ghost" style={{ marginTop: 10 }} onClick={() => setAll((v) => !v)}>
          {all ? "Show less" : "View all activity"}
        </button>
      )}
    </>
  );
}

/* ------------------------------ KPI card ------------------------------ */
function Kpi({
  icon,
  label,
  value,
  sub,
  tone,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  sub?: ReactNode;
  tone?: "danger" | "ok";
  onClick: () => void;
}) {
  return (
    <button className={`kpi ${tone ? `tone-${tone}` : ""}`} onClick={onClick}>
      <span className="kpi-icon">{icon}</span>
      <div className="kpi-main">
        <span className="kpi-label">{label}</span>
        <div className="kpi-value">{value}</div>
        {sub && <div className="kpi-sub">{sub}</div>}
      </div>
    </button>
  );
}


/* ----------------------------- traceability ----------------------------- */
function TraceHealth({
  requirements,
  testCases,
  executions,
  defects,
  reqsNoTests,
  uncovered,
  linkHealth,
  onOpen,
  onMatrix,
}: {
  requirements: number;
  testCases: number;
  executions: number;
  defects: number;
  reqsNoTests: number;
  uncovered: string | null;
  linkHealth: Metric | undefined;
  onOpen: (m: string) => void;
  onMatrix: () => void;
}) {
  const node = (label: string, value: number, icon: ReactNode) => (
    <div className="trace-node">
      <span className="n-ic">{icon}</span>
      <span className="n-value">{value}</span>
      <span className="n-label">{label}</span>
    </div>
  );
  const warn = (text: string, action: ReactNode) => (
    <div className="trace-warn">
      <span className="w-text">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
        </svg>
        {text}
      </span>
      {action}
    </div>
  );
  return (
    <>
      <div className="trace-flow">
        {node("Requirements", requirements, Icons.requirements)}
        <span className="trace-arrow">→</span>
        {node("Test Cases", testCases, Icons.repository)}
        <span className="trace-arrow">→</span>
        {node("Executions", executions, Icons.cycles)}
        <span className="trace-arrow">→</span>
        {node("Defects", defects, Icons.bug)}
      </div>
      <div style={{ marginTop: 10 }}>
        {reqsNoTests > 0 &&
          warn(`${reqsNoTests} requirement${reqsNoTests === 1 ? "" : "s"} without tests`,
            <button className="btn sm" onClick={() => onOpen("M-09")}>View</button>)}
        {uncovered && uncovered !== "0" &&
          warn(`${uncovered} uncovered active requirement${uncovered === "1" ? "" : "s"}`,
            <button className="btn sm" onClick={() => onOpen("M-09")}>View</button>)}
        {linkHealth && linkHealth.value !== null && linkHealth.value < 1 &&
          warn(`Trace-link health at ${pct(linkHealth.value)}`,
            <button className="btn sm" onClick={() => onOpen("M-13")}>View</button>)}
        <div className="trace-warn">
          <span className="w-text muted">Full requirement → test → result map</span>
          <button className="btn sm primary" onClick={onMatrix}>Open traceability matrix</button>
        </div>
      </div>
    </>
  );
}

/* --------------------------- release readiness --------------------------- */
function ReleaseReadiness({
  passRate,
  completion,
  coverage,
  openCritical,
  blocked,
  onReport,
}: {
  passRate: number | null;
  completion: number | null;
  coverage: number | null;
  openCritical: number;
  blocked: number;
  onReport: () => void;
}) {
  const base =
    0.35 * (passRate ?? 0) + 0.25 * (completion ?? 0) + 0.4 * (coverage ?? 0);
  const score = Math.max(0, Math.min(100, Math.round(base * 100) - openCritical * 6 - blocked * 2));
  const tone: "good" | "warn" | "bad" = score >= 80 ? "good" : score >= 60 ? "warn" : "bad";
  const label = score >= 80 ? "On track" : score >= 60 ? "At risk" : "Not ready";
  const row = (text: string, ok: boolean, val: string) => (
    <div className="gauge-check-row">
      {ok ? (
        <svg className="ok" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
      ) : (
        <svg className="bad" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>
      )}
      <span>{text}</span>
      <span className="val">{val}</span>
    </div>
  );
  return (
    <div className="gauge-wrap">
      <Gauge value={score} label={label} tone={tone} />
      <div className="gauge-check">
        {row("Design coverage", (coverage ?? 0) >= 0.8, pct(coverage))}
        {row("Pass rate", (passRate ?? 0) >= 0.8, pct(passRate))}
        {row("Open critical defects", openCritical === 0, String(openCritical))}
        {row("Blocked tests", blocked === 0, String(blocked))}
        <button className="btn sm primary" style={{ marginTop: 4, alignSelf: "flex-start" }} onClick={onReport}>
          View release report
        </button>
      </div>
    </div>
  );
}

/* ------------------------------ metric row ------------------------------ */
function MetricRow({ m, onOpen }: { m: Metric; onOpen: () => void }) {
  const meta = META[m.metric_id];
  return (
    <button className="metric-row" title={meta?.help} onClick={onOpen}>
      <div className="metric-row-label">
        {meta?.name ?? m.label}
        <span className="drill-hint">↗</span>
      </div>
      {m.kind === "ratio" ? (
        <>
          <div className="mbar">
            <span style={{ width: `${Math.round((m.value ?? 0) * 100)}%`, background: "var(--primary)" }} />
          </div>
          <div className="metric-row-value">
            {m.display}
            <span className="muted">{m.denominator !== null ? ` · ${m.numerator}/${m.denominator}` : ""}</span>
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
            <span className="muted small">{r.cycle_count} cycles · {r.requirements} requirements</span>
            {r.open_critical_defects > 0 && <span className="badge FAILED">{r.open_critical_defects} open critical</span>}
            <span className="drill-hint" style={{ marginLeft: "auto" }}>
              {activeReleaseId === r.release_id ? "scoped ✓" : "scope to this"}
            </span>
          </button>
          <div className="cycle-row-metrics" style={{ marginTop: 8 }}>
            <div>
              <div className="cm-label">Completion</div>
              <div className="mbar"><span style={{ width: `${Math.round((r.completion ?? 0) * 100)}%`, background: "var(--primary)" }} /></div>
              <div className="cm-value">{pct1(r.completion)} · {r.terminal}/{r.scoped_tests}</div>
            </div>
            <div>
              <div className="cm-label">Pass rate</div>
              <div className="mbar"><span style={{ width: `${Math.round((r.pass_rate ?? 0) * 100)}%`, background: (r.pass_rate ?? 0) >= 0.8 ? "var(--success-solid)" : "var(--viz-block)" }} /></div>
              <div className="cm-value">{pct1(r.pass_rate)}</div>
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

/* ================================ page ================================ */
export function DashboardPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const nav = useNavigate();
  const [releaseId, setReleaseId] = useState("");
  const [cycleId, setCycleId] = useState("");
  const [environment, setEnvironment] = useState("");
  const [openMetric, setOpenMetric] = useState<string | null>(null);

  const allProjects = useProjects();
  const refValues = useList<ReferenceValue[]>(["refs", pid], `/projects/${pid}/reference-values`, !!pid);
  const environments = (refValues.data ?? []).filter((r) => r.kind === "environment" && r.is_active);
  const activity = useList<{ items: ActivityItem[] }>(["activity", pid], `/projects/${pid}/activity?limit=15`, !!pid);
  const trend = useList<{ series: TrendPoint[] }>(
    ["exec-trend", pid, releaseId, cycleId, environment],
    `/projects/${pid}/reports/execution-trend?${new URLSearchParams({
      ...(releaseId ? { release_id: releaseId } : {}),
      ...(cycleId ? { cycle_id: cycleId } : {}),
      ...(environment ? { environment } : {}),
      days: "30",
    }).toString()}`,
    !!pid,
  );
  const releases = useList<Paginated<Release>>(["releases", pid], `/projects/${pid}/releases?page_size=200`, !!pid);
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
  if (environment) scopeParams.environment = environment;
  const query = new URLSearchParams(scopeParams).toString();

  const coverageType = useList<CoverageByType>(
    ["coverage-by-type", pid, releaseId, cycleId, environment],
    `/projects/${pid}/reports/coverage-by-type?${query}`,
    !!pid,
  );
  const defects = useList<Paginated<Defect>>(["defects", pid], `/projects/${pid}/defects?page_size=200`, !!pid);
  const matrix = useList<{ rows: MatrixRow[] }>(["matrix", pid], `/projects/${pid}/traceability/matrix`, !!pid);
  const requirements = useList<Paginated<Requirement>>(["reqs", pid], `/projects/${pid}/requirements?page_size=200`, !!pid);
  const tcCount = useList<Paginated<TestCase>>(["tc-count", pid], `/projects/${pid}/test-cases?page_size=1`, !!pid);

  const summary = useQuery({
    queryKey: ["summary", pid, releaseId, cycleId, environment],
    queryFn: () => http.get<ReportSummary>(`/projects/${pid}/reports/summary?${query}`),
    enabled: !!pid,
  });
  const breakdown = useQuery({
    queryKey: ["cycle-breakdown", pid, releaseId, cycleId, environment],
    queryFn: () => http.get<{ cycles: CycleBreakdownRow[] }>(`/projects/${pid}/reports/cycle-breakdown?${query}`),
    enabled: !!pid,
  });

  if (!project) return <p>Loading project…</p>;

  const byId: Record<string, Metric> = Object.fromEntries((summary.data?.metrics ?? []).map((m) => [m.metric_id, m]));
  const relRows = releaseOverview.data?.releases ?? [];
  const cyc = breakdown.data?.cycles ?? [];
  const activeRelease = releases.data?.items.find((r) => r.id === releaseId);

  const totals = cyc.reduce(
    (a, c) => ({
      passed: a.passed + c.passed, failed: a.failed + c.failed,
      blocked: a.blocked + c.blocked, not_run: a.not_run + c.not_run, scoped: a.scoped + c.scoped,
    }),
    { passed: 0, failed: 0, blocked: 0, not_run: 0, scoped: 0 },
  );
  const execTotal = totals.passed + totals.failed + totals.blocked + totals.not_run;

  const openDefects = (defects.data?.items ?? []).filter(
    (d) => !["closed", "rejected"].includes(d.status),
  );
  const sevBuckets = ["critical", "high", "medium", "low"].map((s) => ({
    label: s[0].toUpperCase() + s.slice(1),
    value: openDefects.filter((d) => d.severity === s).length,
  }));
  const sevMax = Math.max(1, ...sevBuckets.map((b) => b.value));

  const matrixRows = matrix.data?.rows ?? [];
  const reqsNoTests = matrixRows.filter((r) => r.linked_test_case_keys.length === 0).length;

  const coveredKeys = new Set(
    matrixRows.filter((r) => r.linked_test_case_keys.length > 0).map((r) => r.requirement_key),
  );
  const prioBuckets = ["critical", "high", "medium", "low"]
    .map((p) => {
      const reqs = (requirements.data?.items ?? []).filter((r) => r.status === "active" && r.priority === p);
      const covered = reqs.filter((r) => coveredKeys.has(r.key)).length;
      return {
        label: p[0].toUpperCase() + p.slice(1),
        total: reqs.length,
        value: reqs.length ? covered / reqs.length : 0,
        covered,
      };
    })
    .filter((b) => b.total > 0);

  const m = (id: string) => byId[id];
  const kpiVal = (id: string) => {
    const x = m(id);
    if (!x) return "–";
    if (x.kind === "ratio") return x.value === null ? "–" : `${Math.round(x.value * 100)}%`;
    return x.display;
  };

  return (
    <>
      <div className="filter-bar">
        <span className="filter-chip">
          Project
          <select value={project.key} onChange={(e) => nav(`/p/${e.target.value}/dashboard`)} aria-label="Switch project">
            {(allProjects.data ?? [project]).map((p) => (
              <option key={p.key} value={p.key}>{p.name}</option>
            ))}
          </select>
        </span>
        <span className="filter-chip">
          Release
          <select value={releaseId} onChange={(e) => { setReleaseId(e.target.value); setCycleId(""); }} aria-label="Release scope">
            <option value="">All</option>
            {releases.data?.items.map((r) => (
              <option key={r.id} value={r.id}>{r.version_label || r.key}</option>
            ))}
          </select>
        </span>
        <span className="filter-chip">
          Environment
          <select value={environment} onChange={(e) => setEnvironment(e.target.value)} aria-label="Environment scope">
            <option value="">All</option>
            {environments.map((e) => (
              <option key={e.id} value={e.value} style={{ textTransform: "capitalize" }}>
                {e.value[0].toUpperCase() + e.value.slice(1)}
              </option>
            ))}
          </select>
        </span>
        <span className="filter-chip">
          Cycle
          <select value={cycleId} onChange={(e) => setCycleId(e.target.value)} aria-label="Cycle scope">
            <option value="">{releaseId ? "All in release" : "All"}</option>
            {cycles.data?.map((c) => (
              <option key={c.id} value={c.id}>{c.key} · {c.name}</option>
            ))}
          </select>
        </span>
        {activeRelease && <span className="pill">Scoped: {activeRelease.version_label || activeRelease.key}</span>}
        {pid && (
          <a className="btn sm" style={{ marginLeft: "auto" }} href={`${API_BASE}/projects/${pid}/reports/summary.csv?${query}`}>
            Export CSV
          </a>
        )}
      </div>

      {summary.isLoading && <p>Computing metrics…</p>}

      {summary.data && (
        <>
          <div className="kpi-grid">
            <Kpi
              icon={Icons.requirements} label="Requirements Coverage" value={kpiVal("M-05")}
              sub={m("M-05")?.denominator != null ? `${m("M-05").numerator} of ${m("M-05").denominator} requirements` : "no requirements"}
              onClick={() => setOpenMetric("M-05")}
            />
            <Kpi
              icon={Icons.play} label="Execution Progress" value={kpiVal("M-02")}
              sub={m("M-02")?.denominator != null ? `${m("M-02").numerator} / ${m("M-02").denominator} executed` : "no cycle tests"}
              onClick={() => setOpenMetric("M-02")}
            />
            <Kpi
              icon={Icons.checkCircle} label="Pass Rate" value={kpiVal("M-03")} tone="ok"
              sub={m("M-03")?.denominator != null ? `${m("M-03").numerator} / ${m("M-03").denominator} conclusive` : "nothing run"}
              onClick={() => setOpenMetric("M-03")}
            />
            <Kpi
              icon={Icons.bug} label="Open Defects" value={String(openDefects.length)} tone="danger"
              sub={<span style={{ color: "var(--danger)", fontWeight: 700 }}>{sevBuckets[0].value} critical</span>}
              onClick={() => setOpenMetric("M-10")}
            />
            <Kpi
              icon={Icons.robot} label="Automation Coverage" value={kpiVal("M-12")}
              sub={m("M-12")?.denominator != null ? `${m("M-12").numerator} / ${m("M-12").denominator} eligible` : "none eligible"}
              onClick={() => setOpenMetric("M-12")}
            />
          </div>

          <div className="dash-grid r4">
            <FixedCard title="Execution Trend" action={<button className="link btn sm ghost" onClick={() => nav(`/p/${projectKey}/cycles`)}>Open</button>}>
              {(trend.data?.series ?? []).some((d) => d.total > 0) ? (
                <TrendChart series={trend.data!.series} />
              ) : (
                <p className="muted">No executions recorded in the last 30 days.</p>
              )}
            </FixedCard>

            <FixedCard title="Test Status">
              {execTotal === 0 ? (
                <p className="muted">Nothing scoped yet.</p>
              ) : (
                <Donut
                  size={132}
                  centerLabel="scoped"
                  centerValue={String(execTotal)}
                  segments={[
                    { label: "Passed", value: totals.passed, varName: "--viz-pass" },
                    { label: "Failed", value: totals.failed, varName: "--viz-fail" },
                    { label: "Blocked", value: totals.blocked, varName: "--viz-block" },
                    { label: "Not run", value: totals.not_run, varName: "--viz-notrun" },
                  ]}
                />
              )}
            </FixedCard>

            <FixedCard title="Coverage by requirement priority">
              {prioBuckets.length === 0 ? (
                <p className="muted">No active requirements yet.</p>
              ) : (
                <HBars
                  rows={prioBuckets.map((b) => ({
                    label: b.label,
                    value: b.value,
                    max: 1,
                    display: pct(b.value),
                    color: b.value >= 0.85 ? "var(--viz-pass)" : b.value >= 0.6 ? "var(--viz-block)" : "var(--viz-fail)",
                    onClick: () => setOpenMetric("M-05"),
                  }))}
                />
              )}
            </FixedCard>

            <FixedCard title="Open defects by severity" action={<button className="link btn sm ghost" onClick={() => nav(`/p/${projectKey}/defects`)}>Open</button>}>
              {openDefects.length === 0 ? (
                <p className="muted">No open defects.</p>
              ) : (
                <HBars
                  rows={sevBuckets.map((b) => ({
                    label: b.label,
                    value: b.value,
                    max: sevMax,
                    display: String(b.value),
                    color: b.label === "Critical" || b.label === "High" ? "var(--viz-fail)" : "var(--viz-block)",
                  }))}
                />
              )}
            </FixedCard>
          </div>

          <div className="dash-grid r3">
            <FixedCard title="Traceability health">
              <TraceHealth
                requirements={matrixRows.length}
                testCases={tcCount.data?.total ?? 0}
                executions={totals.scoped}
                defects={defects.data?.total ?? 0}
                reqsNoTests={reqsNoTests}
                uncovered={m("M-09")?.display ?? null}
                linkHealth={m("M-13")}
                onOpen={setOpenMetric}
                onMatrix={() => nav(`/p/${projectKey}/traceability`)}
              />
            </FixedCard>

            <FixedCard title="Release readiness">
              <ReleaseReadiness
                passRate={m("M-03")?.value ?? null}
                completion={m("M-02")?.value ?? null}
                coverage={m("M-05")?.value ?? null}
                openCritical={m("M-10") ? Number(m("M-10").numerator ?? m("M-10").value ?? 0) : sevBuckets[0].value}
                blocked={totals.blocked}
                onReport={() => nav(`/p/${projectKey}/releases`)}
              />
            </FixedCard>

            <FixedCard title="Recent activity">
              <RecentActivity items={activity.data?.items ?? []} />
            </FixedCard>
          </div>

          <div className="dash-grid g-2col">
            <Card>
              <div className="card-title">Quality signals</div>
              <div className="metric-list">
                {["M-11", "M-13", "M-09"].filter((id) => m(id)).map((id) => (
                  <MetricRow key={id} m={m(id)} onOpen={() => setOpenMetric(id)} />
                ))}
              </div>
            </Card>

            <Card>
              <div className="card-title">Automation split</div>
              {coverageType.data ? (
                <Donut
                  centerLabel="active tests"
                  centerValue={String(coverageType.data.tests.total)}
                  segments={[
                    { label: "Automated", value: coverageType.data.tests.automated, varName: "--viz-cat-1" },
                    { label: "Manual", value: coverageType.data.tests.manual, varName: "--viz-cat-2" },
                    { label: "N/A", value: coverageType.data.tests.not_applicable, varName: "--viz-cat-3" },
                  ]}
                />
              ) : (
                <p className="muted">Loading…</p>
              )}
            </Card>
          </div>

          {relRows.length > 0 && (
            <Card>
              <div className="card-title">Releases</div>
              <ReleaseRollup
                rows={relRows}
                activeReleaseId={releaseId}
                onPickRelease={(id) => { setReleaseId(id); setCycleId(""); }}
                onOpenCycles={() => nav(`/p/${projectKey}/cycles`)}
              />
            </Card>
          )}

          {summary.data.metrics.length === 0 && (
            <EmptyState>
              No metric data yet. Add requirements, link tests, then run a cycle to see coverage and pass rates here.
            </EmptyState>
          )}
        </>
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
