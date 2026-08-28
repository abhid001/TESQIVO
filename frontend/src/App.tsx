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
import { Logo } from "./components/Logo";
import { Icons } from "./components/icons";
import { LoginPage } from "./pages/LoginPage";
import { SetupPage } from "./pages/SetupPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
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

const TABS = [
  { to: "dashboard", label: "Dashboard", section: "dashboard", accent: "var(--sec-dashboard)", icon: Icons.dashboard },
  { to: "tests", label: "Tests", section: "tests", accent: "var(--sec-repository)", icon: Icons.repository },
  { to: "scenarios", label: "Scenarios", section: "scenarios", accent: "var(--sec-scenarios)", icon: Icons.scenarios },
  { to: "plans", label: "Plans", section: "plans", accent: "var(--sec-plans)", icon: Icons.plans },
  { to: "cycles", label: "Cycles", section: "cycles", accent: "var(--sec-cycles)", icon: Icons.cycles },
  { to: "releases", label: "Releases", section: "releases", accent: "var(--sec-releases)", icon: Icons.releases },
  { to: "traceability", label: "Traceability", section: "traceability", accent: "var(--sec-traceability)", icon: Icons.traceability },
  { to: "backlog", label: "Requirements & Defects", section: "backlog", accent: "var(--sec-backlog)", icon: Icons.backlog },
] as const;

const SETTINGS_TAB = {
  to: "settings", label: "Settings", section: "settings",
  accent: "var(--sec-releases)", icon: Icons.settings,
} as const;

function Shell() {
  const { projectKey } = useParams();
  const { me, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const projects = useProjects();
  const { project } = useProject(projectKey);
  const role = useRole(project?.id);

  const tabs = canManageProject(role) ? [...TABS, SETTINGS_TAB] : TABS;
  const current =
    tabs.find((t) => loc.pathname.includes(`/${t.to}`)) ?? tabs[0];

  return (
    <div className="app">
      <div className="appbar">
      <header className="topbar">
        <div className="brand">
          <Logo size={26} />
          <span>TESQIVO</span>
        </div>
        <select
          className="project-chip"
          value={projectKey}
          onChange={(e) => nav(`/p/${e.target.value}/${current.to}`)}
          aria-label="Switch project"
        >
          {projects.data?.map((p) => (
            <option key={p.id} value={p.key}>
              {p.key} · {p.name}
            </option>
          ))}
        </select>
        <div className="spacer" />
        <div className="user">
          {me?.is_system_admin && (
            <button className="sm" onClick={() => nav("/admin")}>Admin console</button>
          )}
          <span>{me?.display_name}</span>
          <button className="sm" onClick={() => void logout()}>
            Sign out
          </button>
        </div>
      </header>

      <nav className="tabbar" aria-label="Sections">
        {tabs.map((t) => {
          const active = current.to === t.to;
          return (
            <button
              key={t.to}
              className={`tab ${active ? "active" : ""}`}
              style={{ ["--accent" as string]: t.accent }}
              aria-current={active ? "page" : undefined}
              onClick={() => nav(`/p/${projectKey}/${t.to}`)}
            >
              <span className="tab-icon">{t.icon}</span>
              {t.label}
            </button>
          );
        })}
      </nav>
      </div>

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
          <Route path="backlog" element={<BacklogPage />} />
          <Route path="settings" element={<ProjectSettingsPage />} />
          <Route path="*" element={<Navigate to="dashboard" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  const { me, loading } = useAuth();
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null);

  useEffect(() => {
    http
      .get<{ needs_setup: boolean }>("/setup/status")
      .then((r) => setNeedsSetup(r.needs_setup))
      .catch(() => setNeedsSetup(false));
  }, [me]);

  if (loading || needsSetup === null) return <div className="centered">Loading…</div>;
  if (needsSetup) return <SetupPage onDone={() => setNeedsSetup(false)} />;
  if (!me) return <LoginPage />;
  if (me.must_change_password) return <ChangePasswordPage forced />;

  return (
    <Routes>
      <Route path="/" element={me.is_system_admin ? <Navigate to="/admin" replace /> : <ProjectPicker />} />
      <Route path="/projects" element={<ProjectPicker />} />
      <Route path="/admin/*" element={<AdminConsole />} />
      <Route path="/p/:projectKey/*" element={<Shell />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
