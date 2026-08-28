import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { Logo } from "../../components/Logo";
import { Icons } from "../../components/icons";
import { AdminUsers } from "./AdminUsers";
import { AdminProjects } from "./AdminProjects";

export function AdminConsole() {
  const { me, logout } = useAuth();
  const nav = useNavigate();
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
          <div className="user">
            <button className="sm" onClick={() => nav("/projects")}>Open a project</button>
            <span>{me.display_name}</span>
            <button className="sm" onClick={() => void logout()}>Sign out</button>
          </div>
        </header>
        <nav className="tabbar" aria-label="Admin sections">
          <NavLink to="/admin/users" className={({ isActive }) => `tab ${isActive ? "active" : ""}`} style={{ ["--accent" as string]: "#0f766e" }}>
            <span className="tab-icon">{Icons.admin}</span>
            Users
          </NavLink>
          <NavLink to="/admin/projects" className={({ isActive }) => `tab ${isActive ? "active" : ""}`} style={{ ["--accent" as string]: "#0ea5e9" }}>
            <span className="tab-icon">{Icons.releases}</span>
            Projects
          </NavLink>
        </nav>
      </div>
      <main className="main">
        <Routes>
          <Route path="users" element={<AdminUsers />} />
          <Route path="projects" element={<AdminProjects />} />
          <Route path="*" element={<Navigate to="users" replace />} />
        </Routes>
      </main>
    </div>
  );
}
