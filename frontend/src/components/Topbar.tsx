import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import type { Notification } from "../api/types";
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

function relTime(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

function Notifications() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const q = useQuery({
    queryKey: ["notifications"],
    queryFn: () => http.get<{ items: Notification[]; unread: number }>("/notifications?limit=25"),
    refetchInterval: 30000,
    refetchOnWindowFocus: true,
  });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["notifications"] });
  const markRead = useMutation({
    mutationFn: (id: string) => http.post(`/notifications/${id}/read`),
    onSuccess: invalidate,
  });
  const markAll = useMutation({
    mutationFn: () => http.post("/notifications/read-all"),
    onSuccess: invalidate,
  });

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

  const unread = q.data?.unread ?? 0;
  const items = q.data?.items ?? [];

  const openItem = (n: Notification) => {
    if (!n.read) markRead.mutate(n.id);
    if (n.link) {
      setOpen(false);
      nav(n.link);
    }
  };

  return (
    <div className="app-menu" ref={ref}>
      <button className="icon-round" onClick={() => setOpen((v) => !v)} aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}>
        {BellIcon}
        {unread > 0 && <span className="notif-badge">{unread > 9 ? "9+" : unread}</span>}
      </button>
      {open && (
        <div className="app-menu-panel notif-panel" role="menu">
          <div className="notif-head">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button className="btn sm ghost" onClick={() => markAll.mutate()} disabled={markAll.isPending}>
                Mark all as read
              </button>
            )}
          </div>
          <div className="notif-list">
            {items.length === 0 && <p className="muted small" style={{ padding: "12px" }}>You’re all caught up.</p>}
            {items.map((n) => (
              <button
                key={n.id}
                className={`notif-item ${n.read ? "" : "unread"}`}
                onClick={() => openItem(n)}
              >
                <div className="notif-item-body">
                  <div className="notif-item-title">{n.title}</div>
                  {n.body && <div className="muted small notif-item-text">{n.body}</div>}
                  <div className="notif-item-time">{relTime(n.created_at)}</div>
                </div>
                {!n.read && (
                  <span
                    className="notif-mark"
                    role="button"
                    title="Mark as read"
                    onClick={(e) => { e.stopPropagation(); markRead.mutate(n.id); }}
                  >
                    ✓
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Global top bar: optional page title + optional brand + search + notifications + account menu. */
export function Topbar({
  onToggleNav,
  onSearch,
  searchPlaceholder = "Search this project…",
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
        <Notifications />
        <AppMenu />
      </div>
    </header>
  );
}
