import { useState } from "react";
import { http } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Card, Field, PASSWORD_HINT, errText } from "../ui";
import { Logo } from "../components/Logo";

export function ChangePasswordPage({ forced = false }: { forced?: boolean }) {
  const { refresh, logout } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (next !== confirm) {
      setError("The new passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await http.post("/auth/password", { current_password: current, new_password: next });
      setDone(true);
      await refresh();
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-shell">
      <Card className="auth-card">
        <div className="brand-lockup" style={{ color: "var(--primary)" }}>
          <Logo size={28} />
          TESQIVO
        </div>
        <h2 style={{ marginTop: 4 }}>
          {forced ? "Set a new password" : "Change your password"}
        </h2>
        {forced && (
          <p className="muted">
            You signed in with a temporary password. Choose a new one to continue.
          </p>
        )}
        {done && !forced ? (
          <p className="notice ok">Password updated.</p>
        ) : (
          <form onSubmit={submit} className="stack">
            <Field label={forced ? "Temporary password" : "Current password"}>
              <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoFocus />
            </Field>
            <Field label="New password" hint={PASSWORD_HINT}>
              <input type="password" value={next} onChange={(e) => setNext(e.target.value)} />
            </Field>
            <Field label="Confirm new password" error={error ?? undefined}>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </Field>
            <button className="primary" style={{ width: "100%", justifyContent: "center" }} disabled={busy || !current || !next}>
              {busy ? "Updating…" : "Update password"}
            </button>
          </form>
        )}
        <button className="ghost sm" style={{ marginTop: 12 }} onClick={() => void logout()}>
          Sign out
        </button>
      </Card>
    </div>
  );
}
