import { useEffect, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { useAuth, useRole, canManageProject } from "./auth/AuthContext";
import { http } from "./api/client";
import { useProject, useProjects } from "./api/hooks";
import { Icons } from "./components/icons";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { FeedbackWidget } from "./components/FeedbackWidget";
import { PlainShell } from "./components/PlainShell";
import { LoginPage } from "./pages/LoginPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SetupPage } from "./pages/SetupPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { ProjectPicker } from "./pages/ProjectPicker";
import { AdminConsole } from "./pages/admin/AdminConsole";
import { ProjectSettingsPage } from "./pages/ProjectSettingsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { RepositoryPage } from "./pages/RepositoryPage";
import { ScenariosPage } from "./pages/ScenariosPage";
import { TestCasePage } from "./pages/TestCasePage";
import { PlansPage } from "./pages/PlansPage";
import { CyclesPage } from "./pages/CyclesPage";
import { CycleRunnerPage } from "./pages/CycleRunnerPage";
import { TraceabilityPage } from "./pages/TraceabilityPage";
import { BacklogPage } from "./pages/BacklogPage";
import { ReleasesPage } from "./pages/ReleasesPage";
import { ReportsPage } from "./pages/ReportsPage";

const TABS = [
  { to: "dashboard", label: "Overview", section: "dashboard", icon: Icons.dashboard },
  { to: "requirements", label: "Requirements", section: "backlog", icon: Icons.requirements },
  { to: "tests", label: "Test Cases", section: "tests", icon: Icons.repository },
  { to: "plans", label: "Test Plans", section: "plans", icon: Icons.plans },
  { to: "cycles", label: "Executions", section: "cycles", icon: Icons.cycles },
  { to: "releases", label: "Releases", section: "releases", icon: Icons.releases },
  { to: "traceability", label: "Traceability", section: "traceability", icon: Icons.traceability },
  { to: "defects", label: "Defects", section: "backlog", icon: Icons.bug },
  { to: "reports", label: "Reports", section: "dashboard", icon: Icons.reports },
] as const;

const SETTINGS_TAB = { to: "settings", label: "Settings", section: "settings", icon: Icons.settings } as const;

/** Route a project-wide search: readable keys jump to their record, free text
 *  falls back to the test-case search. */
function projectSearchPath(projectKey: string, raw: string): string {
  const q = raw.trim();
  const m = q.toUpperCase().match(/-(REQ|DEF|TC|PLAN|REL|SCN)-\d+$/);
  const base = `/p/${projectKey}`;
  if (m) {
    const kind = m[1];
    if (kind === "REQ") return `${base}/requirements?req=${encodeURIComponent(q.toUpperCase())}`;
    if (kind === "DEF") return `${base}/defects?q=${encodeURIComponent(q)}`;
    if (kind === "TC") return `${base}/tests?q=${encodeURIComponent(q)}`;
    if (kind === "PLAN") return `${base}/plans`;
    if (kind === "REL") return `${base}/releases`;
    if (kind === "SCN") return `${base}/scenarios`;
  }
  return `${base}/tests?q=${encodeURIComponent(q)}`;
}

function useCollapsed() {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem("tq.nav.collapsed") === "1"; } catch { return false; }
  });
  const toggle = () => setCollapsed((v) => {
    try { localStorage.setItem("tq.nav.collapsed", v ? "0" : "1"); } catch { /* ignore */ }
    return !v;
  });
  return [collapsed, toggle] as const;
}

function Shell() {
  const { projectKey } = useParams();
  const { me } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const projects = useProjects();
  const { project } = useProject(projectKey);
  const role = useRole(project?.id);
  const [collapsed, toggleCollapsed] = useCollapsed();
  const [navOpen, setNavOpen] = useState(false);

  // System administrators never enter the project shell — they work from the
  // Admin console only.
  if (me?.is_system_admin) return <Navigate to="/admin" replace />;

  // Logged in but not a member of this project (stale link / lost access):
  // don't strand the user on an endless "Loading…" — send them somewhere useful.
  if (projects.isSuccess && !project) {
    return (
      <PlainShell>
        <div className="page-header"><h2>No access to “{projectKey}”</h2></div>
        <p className="muted">
          You’re not a member of this project, or it doesn’t exist. Pick another
          project or request access.
        </p>
        <div className="inline-actions">
          <button className="primary" onClick={() => nav("/projects")}>Go to projects</button>
        </div>
      </PlainShell>
    );
  }

  const tabs = canManageProject(role) ? [...TABS, SETTINGS_TAB] : TABS;
  const current = tabs.find((t) => loc.pathname.includes(`/${t.to}`)) ?? tabs[0];
  const go = (to: string) => { setNavOpen(false); nav(`/p/${projectKey}/${to}`); };

  return (
    <div className={`app ${collapsed ? "collapsed" : ""} ${navOpen ? "nav-open" : ""}`}>
      <Sidebar
        items={tabs.map((t) => ({ to: t.to, label: t.label, icon: t.icon }))}
        activeTo={current.to}
        onNavigate={go}
        onBrand={() => { setNavOpen(false); nav("/"); }}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
      />
      {navOpen && <div className="nav-scrim" onClick={() => setNavOpen(false)} />}

      <div className="content">
        <Topbar
          onToggleNav={() => setNavOpen((v) => !v)}
          onSearch={(q) => nav(projectSearchPath(projectKey!, q))}
          title={current.to === "dashboard" ? "Quality Command Center" : undefined}
          subtitle={current.to === "dashboard" ? project?.name : undefined}
        />
        <main className={`main section-${current.section}`}>
          <Routes>
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="tests" element={<RepositoryPage />} />
            <Route path="tests/:testCaseId" element={<TestCasePage />} />
            <Route path="scenarios" element={<ScenariosPage />} />
            <Route path="repository" element={<Navigate to="../tests" replace />} />
            <Route path="plans" element={<PlansPage />} />
            <Route path="cycles" element={<CyclesPage />} />
            <Route path="cycles/:cycleId/run" element={<CycleRunnerPage />} />
            <Route path="releases" element={<ReleasesPage />} />
            <Route path="traceability" element={<TraceabilityPage />} />
            <Route path="requirements" element={<BacklogPage view="requirements" />} />
            <Route path="defects" element={<BacklogPage view="defects" />} />
            <Route path="reports" element={<ReportsPage />} />
            <Route path="backlog" element={<Navigate to="../requirements" replace />} />
            <Route path="settings" element={<ProjectSettingsPage />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
          </Routes>
        </main>
      </div>
      <FeedbackWidget projectId={project?.id} />
    </div>
  );
}

export function App() {
  const { me, loading } = useAuth();
  const { pathname } = useLocation();
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);

  useEffect(() => {
    http
      .get<{ needs_setup: boolean }>("/setup/status")
      .then((r) => setNeedsSetup(r.needs_setup))
      .catch(() => setNeedsSetup(false));
  }, [me]);

  // Public reset-link page - reachable while signed out (or signed in on another device).
  if (pathname === "/reset") return <ResetPasswordPage />;
  if (loading || needsSetup === null) return <div className="centered">Loading…</div>;
  if (needsSetup) return <SetupPage onDone={() => setNeedsSetup(false)} />;
  if (!me) return <LoginPage />;
  if (me.must_change_password) return <ChangePasswordPage forced />;

  return (
    <Routes>
      <Route path="/" element={me.is_system_admin ? <Navigate to="/admin" replace /> : <ProjectPicker />} />
      <Route path="/projects" element={<ProjectPicker />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/admin/*" element={<AdminConsole />} />
      <Route path="/p/:projectKey/*" element={<Shell />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
