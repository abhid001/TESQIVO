import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppMenu } from "./AppMenu";
import { Logo } from "./Logo";

const SearchIcon = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
    <circle cx="11" cy="11" r="7" />
    <path d="M21 21l-4.3-4.3" />
  </svg>
);
const BellIcon = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.7 21a2 2 0 0 1-3.4 0" />
  </svg>
);
const MenuIcon = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
    <path d="M3 6h18M3 12h18M3 18h18" />
  </svg>
);

/** Global top bar: optional page title + optional brand + search + notifications + account menu. */
export function Topbar({
  onToggleNav,
  onSearch,
  searchPlaceholder = "Search test cases…",
  brand = false,
  title,
  subtitle,
}: {
  onToggleNav?: () => void;
  onSearch?: (q: string) => void;
  searchPlaceholder?: string;
  brand?: boolean;
  title?: string;
  subtitle?: string;
}) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [bellOpen, setBellOpen] = useState(false);
  const bellRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!bellOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (bellRef.current && !bellRef.current.contains(e.target as Node)) setBellOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [bellOpen]);

  const search = onSearch && (
    <form
      className={`topbar-search ${title ? "compact" : ""}`}
      onSubmit={(e) => {
        e.preventDefault();
        if (q.trim()) onSearch(q.trim());
      }}
    >
      {SearchIcon}
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={searchPlaceholder}
        aria-label="Search"
      />
    </form>
  );

  return (
    <header className={`topbar ${title ? "has-title" : ""}`}>
      {onToggleNav && (
        <button className="icon-round nav-toggle" onClick={onToggleNav} aria-label="Open menu">
          {MenuIcon}
        </button>
      )}
      {brand && (
        <button className="brand-btn" onClick={() => nav("/")} aria-label="Home">
          <Logo size={24} />
          <span>TESQIVO</span>
        </button>
      )}
      {title && (
        <div className="topbar-title">
          <h1>{title}</h1>
          {subtitle && <span>{subtitle}</span>}
        </div>
      )}
      {!title && search}
      <div className="spacer" />
      {title && search}
      <div className="topbar-actions">
        <div className="app-menu" ref={bellRef}>
          <button className="icon-round" onClick={() => setBellOpen((v) => !v)} aria-label="Notifications">
            {BellIcon}
          </button>
          {bellOpen && (
            <div className="app-menu-panel" style={{ minWidth: 240 }} role="menu">
              <div className="app-menu-id-text" style={{ padding: "10px 12px" }}>
                <strong>Notifications</strong>
                <span className="muted">You’re all caught up.</span>
              </div>
            </div>
          )}
        </div>
        <AppMenu />
      </div>
    </header>
  );
}
