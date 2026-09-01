import { useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { Icons } from "../../components/icons";
import { Sidebar } from "../../components/Sidebar";
import { Topbar } from "../../components/Topbar";
import { FeedbackWidget } from "../../components/FeedbackWidget";
import { AdminUsers } from "./AdminUsers";
import { AdminProjects } from "./AdminProjects";
import { AdminRequests } from "./AdminRequests";
import { AdminFeedback } from "./AdminFeedback";

const NAV = [
  { to: "users", label: "Users", icon: Icons.admin },
  { to: "projects", label: "Projects", icon: Icons.releases },
  { to: "requests", label: "Access requests", icon: Icons.traceability },
  { to: "feedback", label: "Feedback", icon: Icons.backlog },
];

export function AdminConsole() {
  const { me } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [navOpen, setNavOpen] = useState(false);
  if (!me?.is_system_admin) return <Navigate to="/" replace />;

  const active = NAV.find((n) => loc.pathname.includes(`/admin/${n.to}`))?.to ?? "users";

  return (
    <div className={`app ${navOpen ? "nav-open" : ""}`}>
      <Sidebar
        label="TESQIVO Admin"
        items={NAV}
        activeTo={active}
        onNavigate={(to) => { setNavOpen(false); nav(`/admin/${to}`); }}
        onBrand={() => nav("/admin")}
      />
      {navOpen && <div className="nav-scrim" onClick={() => setNavOpen(false)} />}
      <div className="content">
        <Topbar onToggleNav={() => setNavOpen((v) => !v)} />
        <main className="main">
          <Routes>
            <Route path="users" element={<AdminUsers />} />
            <Route path="projects" element={<AdminProjects />} />
            <Route path="requests" element={<AdminRequests />} />
            <Route path="feedback" element={<AdminFeedback />} />
            <Route path="*" element={<Navigate to="users" replace />} />
          </Routes>
        </main>
      </div>
      <FeedbackWidget />
    </div>
  );
}
