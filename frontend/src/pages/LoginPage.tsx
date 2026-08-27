import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Card, Field, errText } from "../ui";

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
    <div className="centered">
      <Card className="auth-card">
        <h2>Sign in to TESQIVO</h2>
        <form onSubmit={submit}>
          <Field label="Username">
            <input value={username} onChange={(e) => setU(e.target.value)} autoFocus />
          </Field>
          <Field label="Password" error={error ?? undefined}>
            <input
              type="password"
              value={password}
              onChange={(e) => setP(e.target.value)}
            />
          </Field>
          <button className="primary" disabled={busy || !username || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </Card>
    </div>
  );
}
