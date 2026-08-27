import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { http } from "./api/client";
import { LoginPage } from "./pages/LoginPage";
import { SetupPage } from "./pages/SetupPage";
import { ProjectPicker } from "./pages/ProjectPicker";
import { DashboardPage } from "./pages/DashboardPage";
import { RepositoryPage } from "./pages/RepositoryPage";
import { TestCasePage } from "./pages/TestCasePage";
import { PlansPage } from "./pages/PlansPage";
import { CyclesPage } from "./pages/CyclesPage";
import { CycleRunnerPage } from "./pages/CycleRunnerPage";
import { TraceabilityPage } from "./pages/TraceabilityPage";
import { BacklogPage } from "./pages/BacklogPage";

function Shell() {
  const { projectKey } = useParams();
  const { me, logout } = useAuth();
  const base = `/p/${projectKey}`;
  const link = (to: string, label: string) => (
    <NavLink to={`${base}/${to}`} className={({ isActive }) => (isActive ? "active" : "")}>
      {label}
    </NavLink>
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>TESQIVO</h1>
        <div className="muted" style={{ marginBottom: 12 }}>{projectKey}</div>
        <nav className="stack">
          {link("dashboard", "Dashboard")}
          {link("repository", "Repository")}
          {link("plans", "Plans")}
          {link("cycles", "Cycles")}
          {link("traceability", "Traceability")}
          {link("backlog", "Requirements & Defects")}
          <NavLink to="/">Switch project</NavLink>
        </nav>
        <div style={{ marginTop: 24 }} className="muted">
          {me?.display_name}
          <br />
          <button onClick={() => void logout()} style={{ marginTop: 6 }}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="repository" element={<RepositoryPage />} />
          <Route path="repository/:testCaseId" element={<TestCasePage />} />
          <Route path="plans" element={<PlansPage />} />
          <Route path="cycles" element={<CyclesPage />} />
          <Route path="cycles/:cycleId/run" element={<CycleRunnerPage />} />
          <Route path="traceability" element={<TraceabilityPage />} />
          <Route path="backlog" element={<BacklogPage />} />
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

  return (
    <Routes>
      <Route path="/" element={<ProjectPicker />} />
      <Route path="/p/:projectKey/*" element={<Shell />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
