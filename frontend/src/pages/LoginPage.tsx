import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Card, Field, errText } from "../ui";
import { Logo } from "../components/Logo";

export function LoginPage() {
  const { login } = useAuth();
  const [username, setU] = useState("");
  const [password, setP] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
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
        <p className="muted" style={{ marginTop: 0 }}>
          Sign in to the quality system of record.
        </p>
        <form onSubmit={submit}>
          <Field label="Username">
            <input value={username} onChange={(e) => setU(e.target.value)} autoFocus />
          </Field>
          <Field label="Password" error={error ?? undefined}>
            <input type="password" value={password} onChange={(e) => setP(e.target.value)} />
          </Field>
          <button className="primary" style={{ width: "100%", justifyContent: "center" }} disabled={busy || !username || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </Card>
    </div>
  );
}
