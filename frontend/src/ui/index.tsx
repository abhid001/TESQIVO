import {
  createContext,
  useCallback,
  useContext,
  useEffect,
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
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
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
