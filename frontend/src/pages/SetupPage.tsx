import { useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Card, Field, errText } from "../ui";
import { Logo } from "../components/Logo";

export function SetupPage({ onDone }: { onDone: () => void }) {
  const { login } = useAuth();
  const [f, setF] = useState({
    username: "",
    email: "",
    display_name: "",
    password: "",
    token: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF({ ...f, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/setup", {
        method: "POST",
        headers: { "X-Bootstrap-Token": f.token },
        body: {
          username: f.username,
          email: f.email,
          display_name: f.display_name || f.username,
          password: f.password,
        },
      });
      await login(f.username, f.password);
      onDone();
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
        <h2 style={{ marginTop: 4 }}>Create the first administrator</h2>
        <p className="muted">
          Enter the bootstrap token from your <code>.env</code> and choose an admin
          account. This screen is available only until setup completes.
        </p>
        <form onSubmit={submit} className="stack">
          <Field label="Bootstrap token">
            <input value={f.token} onChange={set("token")} />
          </Field>
          <Field label="Username">
            <input value={f.username} onChange={set("username")} />
          </Field>
          <Field label="Email">
            <input type="email" value={f.email} onChange={set("email")} />
          </Field>
          <Field label="Display name">
            <input value={f.display_name} onChange={set("display_name")} />
          </Field>
          <Field
            label="Password (min 12 chars, mixed case + digit)"
            error={error ?? undefined}
          >
            <input type="password" value={f.password} onChange={set("password")} />
          </Field>
          <button className="primary" disabled={busy}>
            {busy ? "Creating…" : "Create administrator"}
          </button>
        </form>
      </Card>
    </div>
  );
}
