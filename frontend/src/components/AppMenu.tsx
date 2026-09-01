import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Account menu for the top bar: identity summary + profile / password / sign out. */
export function AppMenu() {
  const { me, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!me) return null;

  const go = (path: string) => {
    setOpen(false);
    nav(path);
  };

  return (
    <div className="app-menu" ref={ref}>
      <button
        className="app-menu-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="avatar" aria-hidden>{initials(me.display_name || me.username)}</span>
        <span className="app-menu-name">{me.display_name || me.username}</span>
        <span className="app-menu-caret" aria-hidden>▾</span>
      </button>
      {open && (
        <div className="app-menu-panel" role="menu">
          <div className="app-menu-id">
            <div className="avatar lg" aria-hidden>{initials(me.display_name || me.username)}</div>
            <div className="app-menu-id-text">
              <strong>{me.display_name || me.username}</strong>
              <span className="muted">@{me.username}</span>
              <span className="muted">{me.email}</span>
              {me.is_system_admin && <span className="pill">System administrator</span>}
            </div>
          </div>
          <div className="app-menu-sep" />
          <button role="menuitem" onClick={() => go("/profile")}>Your profile</button>
          <button role="menuitem" onClick={() => go("/profile#password")}>Change password</button>
          {me.is_system_admin ? (
            <button role="menuitem" onClick={() => go("/admin")}>Admin console</button>
          ) : (
            <button role="menuitem" onClick={() => go("/projects")}>Switch project</button>
          )}
          <div className="app-menu-sep" />
          <button role="menuitem" className="danger" onClick={() => void logout()}>Sign out</button>
        </div>
      )}
    </div>
  );
}
