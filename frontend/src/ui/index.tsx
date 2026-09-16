import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { ApiError } from "../api/client";

/** Shown next to every password field. Mirrors the backend policy in
 *  app/core/security.py (password_policy_errors / PASSWORD_POLICY). */
export const PASSWORD_HINT =
  "At least 12 characters, including an upper-case letter, a lower-case letter, a digit, " +
  "and a special character (e.g. ! ? @ # $ % & *). Extra characters beyond these are fine.";

export function Card({
  children,
  className = "",
  style,
  title,
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  title?: string;
}) {
  return (
    <div className={`card ${className}`} style={style} title={title}>
      {children}
    </div>
  );
}

export function Badge({ value }: { value: string }) {
  return <span className={`badge ${value}`}>{value.replaceAll("_", " ")}</span>;
}

/** "in_review" -> "In review" - used for <option> labels drawn from enum values
 *  (priority, status, type, ...), so dropdown lists read as proper words. */
export function cap(value: string): string {
  const s = value.replaceAll("_", " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      <label>
        <span className="field-label">{label}</span>
        {children}
      </label>
      {hint && !error && <div className="hint">{hint}</div>}
      {error && <div className="error">{error}</div>}
    </div>
  );
}

export function Dialog({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  // Forms/dialogs close only via the close button (or a Cancel button inside
  // them) - clicking the dimmed backdrop must not dismiss unsaved work.
  return (
    <div className="dialog-backdrop">
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title}>
        <div className="dialog-head">
          <h2>{title}</h2>
          <button className="ghost sm" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="dialog-body">{children}</div>
      </div>
    </div>
  );
}

/** Right-side sliding panel for an entity's details (Requirements, and other
 *  sections as they adopt the same "click a key -> inspect on the right"
 *  pattern). Like Dialog, it closes only via the close button. */
export function Drawer({
  title,
  subtitle,
  onClose,
  tabs,
  activeTab,
  onTab,
  headerActions,
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  tabs?: string[];
  activeTab?: string;
  onTab?: (t: string) => void;
  headerActions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="drawer-backdrop">
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : "Details"}>
        <div className="drawer-head">
          <div className="drawer-head-text">
            <h3>{title}</h3>
            {subtitle && <div className="muted small">{subtitle}</div>}
          </div>
          <div className="drawer-head-actions">
            {headerActions}
            <button className="ghost sm" onClick={onClose} aria-label="Close">
              ✕
            </button>
          </div>
        </div>
        {tabs && (
          <div className="drawer-tabs" role="tablist">
            {tabs.map((t) => (
              <button
                key={t}
                role="tab"
                aria-selected={activeTab === t}
                className={`drawer-tab ${activeTab === t ? "active" : ""}`}
                onClick={() => onTab?.(t)}
              >
                {t}
              </button>
            ))}
          </div>
        )}
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}

/** Small circular initials badge for a person - "Aarav Desai" -> "AD". */
export function Avatar({ name, size = 26 }: { name: string | null | undefined; size?: number }) {
  const initials = (name ?? "?")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("") || "?";
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.42 }} title={name ?? undefined}>
      {initials}
    </span>
  );
}

/* ---- toasts ---- */
type Toast = { id: number; message: string; kind: "info" | "error" };
const ToastCtx = createContext<(m: string, k?: "info" | "error") => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const idRef = useRef(0);
  const push = useCallback((message: string, kind: "info" | "error" = "info") => {
    const id = ++idRef.current;
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toast-host" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function errText(e: unknown): string {
  if (e instanceof ApiError) {
    const ds = (e.body.details ?? []).filter((d) => d.message);
    if (ds.length === 1) return `${e.body.message} (${ds[0].field}: ${ds[0].message})`;
    if (ds.length > 1) {
      // e.g. all the password rules that failed — show each on its own line.
      return `${e.body.message}\n` + ds.slice(0, 6).map((d) => `• ${d.message}`).join("\n");
    }
    return e.body.message;
  }
  return e instanceof Error ? e.message : "Unexpected error";
}
