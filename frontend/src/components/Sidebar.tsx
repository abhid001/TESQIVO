import type { ReactNode } from "react";
import { Logo } from "./Logo";

export interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

/** Left navigation rail shared by the project shell and the admin console. */
export function Sidebar({
  items,
  activeTo,
  onNavigate,
  onBrand,
  collapsed,
  onToggleCollapsed,
  label = "TESQIVO",
  footer,
}: {
  items: NavItem[];
  activeTo: string;
  onNavigate: (to: string) => void;
  onBrand?: () => void;
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  label?: string;
  footer?: ReactNode;
}) {
  return (
    <aside className="sidebar">
      <button className="sidebar-brand" onClick={onBrand} aria-label="Home">
        <Logo size={26} />
        <span>{label}</span>
      </button>
      <nav className="sidebar-nav" aria-label="Sections">
        {items.map((it) => (
          <button
            key={it.to}
            className={`sidebar-link ${activeTo === it.to ? "active" : ""}`}
            aria-current={activeTo === it.to ? "page" : undefined}
            onClick={() => onNavigate(it.to)}
            title={collapsed ? it.label : undefined}
          >
            {it.icon}
            <span>{it.label}</span>
          </button>
        ))}
        {footer}
      </nav>
      {onToggleCollapsed && (
        <div className="sidebar-foot">
          <button className="sidebar-collapse" onClick={onToggleCollapsed} aria-label="Toggle sidebar">
            <span aria-hidden>{collapsed ? "»" : "«"}</span>
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      )}
    </aside>
  );
}
