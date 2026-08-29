import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { Logo } from "../../components/Logo";
import { Icons } from "../../components/icons";
import { AppMenu } from "../../components/AppMenu";
import { FeedbackWidget } from "../../components/FeedbackWidget";
import { AdminUsers } from "./AdminUsers";
import { AdminProjects } from "./AdminProjects";
import { AdminRequests } from "./AdminRequests";
import { AdminFeedback } from "./AdminFeedback";

const NAV = [
  { to: "users", label: "Users", accent: "#0f766e", icon: Icons.admin },
  { to: "projects", label: "Projects", accent: "#0ea5e9", icon: Icons.releases },
  { to: "requests", label: "Access requests", accent: "#7c3aed", icon: Icons.traceability },
  { to: "feedback", label: "Feedback", accent: "#e0812b", icon: Icons.backlog },
];

export function AdminConsole() {
  const { me } = useAuth();
  if (!me?.is_system_admin) return <Navigate to="/" replace />;

  return (
    <div className="app">
      <div className="appbar">
        <header className="topbar" style={{ background: "linear-gradient(100deg,#0f766e,#0ea5e9)" }}>
          <div className="brand">
            <Logo size={26} />
            <span>TESQIVO Admin</span>
          </div>
          <div className="spacer" />
          <AppMenu />
        </header>
        <nav className="tabbar" aria-label="Admin sections">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={`/admin/${n.to}`}
              className={({ isActive }) => `tab ${isActive ? "active" : ""}`}
              style={{ ["--accent" as string]: n.accent }}
            >
              <span className="tab-icon">{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <main className="main">
        <Routes>
          <Route path="users" element={<AdminUsers />} />
          <Route path="projects" element={<AdminProjects />} />
          <Route path="requests" element={<AdminRequests />} />
          <Route path="feedback" element={<AdminFeedback />} />
          <Route path="*" element={<Navigate to="users" replace />} />
        </Routes>
      </main>
      <FeedbackWidget />
    </div>
  );
}
