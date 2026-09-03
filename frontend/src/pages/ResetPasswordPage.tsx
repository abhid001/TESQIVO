import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { http } from "../api/client";
import { Card, Field, PASSWORD_HINT, errText } from "../ui";
import { Logo } from "../components/Logo";

/** Public page reached from the password-reset email link: /reset?token=... */
export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (next !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await http.post("/auth/password-reset/complete", { token, new_password: next });
      setDone(true);
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
        <h2 style={{ marginTop: 4 }}>Choose a new password</h2>

        {!token ? (
          <p className="notice err">
            This link is missing its token. Request a new reset email from the sign-in page.
          </p>
        ) : done ? (
          <>
            <p className="notice ok">
              Your password has been updated. You can now sign in with it.
            </p>
            <a className="btn primary" style={{ width: "100%", justifyContent: "center", marginTop: 12 }} href="/">
              Go to sign in
            </a>
          </>
        ) : (
          <form onSubmit={submit} className="stack">
            <p className="muted" style={{ marginTop: 0 }}>
              Reset links are valid for one hour and can be used once.
            </p>
            <Field label="New password" hint={PASSWORD_HINT}>
              <input type="password" value={next} onChange={(e) => setNext(e.target.value)} autoFocus />
            </Field>
            <Field label="Confirm new password" error={error ?? undefined}>
              <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </Field>
            <button
              className="primary"
              style={{ width: "100%", justifyContent: "center" }}
              disabled={busy || !next || !confirm}
            >
              {busy ? "Updating…" : "Update password"}
            </button>
            <a className="ghost sm" style={{ marginTop: 4 }} href="/">
              Back to sign in
            </a>
          </form>
        )}
      </Card>
    </div>
  );
}
