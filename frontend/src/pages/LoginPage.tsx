import { useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { http } from "../api/client";
import { Card, Field, errText } from "../ui";
import { Logo } from "../components/Logo";

export function LoginPage() {
  const [mode, setMode] = useState<"login" | "forgot">("login");
  return (
    <div className="auth-shell">
      <Card className="auth-card">
        <div className="brand-lockup" style={{ color: "var(--primary)" }}>
          <Logo size={28} />
          TESQIVO
        </div>
        {mode === "login" ? (
          <LoginForm onForgot={() => setMode("forgot")} />
        ) : (
          <ForgotForm onBack={() => setMode("login")} />
        )}
      </Card>
    </div>
  );
}

function LoginForm({ onForgot }: { onForgot: () => void }) {
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
    <>
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
      <button className="ghost sm" style={{ marginTop: 12 }} onClick={onForgot}>
        Forgot your password?
      </button>
    </>
  );
}

function ForgotForm({ onBack }: { onBack: () => void }) {
  const [identifier, setId] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ outcome: string; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await http.post<{ outcome: string; message: string }>(
        "/auth/password-reset/request",
        { identifier },
      );
      setResult(r);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h2 style={{ marginTop: 4 }}>Reset your password</h2>
      {result ? (
        <>
          <p className={`notice ${result.outcome === "email_sent" ? "ok" : "info"}`}>
            {result.message}
          </p>
          <button className="primary" style={{ width: "100%", justifyContent: "center", marginTop: 12 }} onClick={onBack}>
            Back to sign in
          </button>
        </>
      ) : (
        <form onSubmit={submit} className="stack">
          <p className="muted" style={{ marginTop: 0 }}>
            Enter your username or email. If email is configured on this server and
            your account is eligible, a temporary password will be sent to you.
          </p>
          <Field label="Username or email" error={error ?? undefined}>
            <input value={identifier} onChange={(e) => setId(e.target.value)} autoFocus />
          </Field>
          <button className="primary" style={{ width: "100%", justifyContent: "center" }} disabled={busy || !identifier}>
            {busy ? "Submitting…" : "Request reset"}
          </button>
          <button type="button" className="ghost sm" onClick={onBack}>
            Back to sign in
          </button>
        </form>
      )}
    </>
  );
}
