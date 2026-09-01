import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { http } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { Project } from "../api/types";
import { PlainShell } from "../components/PlainShell";
import { Card, Field, errText } from "../ui";

const ROLE_LABEL: Record<string, string> = {
  project_admin: "Project admin",
  test_manager: "Test manager",
  tester: "Tester",
  viewer: "Viewer",
};

export function ProfilePage() {
  const { me, refresh, logout } = useAuth();
  const pwRef = useRef<HTMLDivElement>(null);
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => http.get<Project[]>("/projects") });

  useEffect(() => {
    if (window.location.hash === "#password") pwRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  if (!me) return null;
  const projName = (id: string) => projects.data?.find((p) => p.id === id)?.name ?? "";

  return (
    <PlainShell>
      <div className="page-header">
        <h2>Your profile</h2>
        <button onClick={() => void logout()}>Sign out</button>
      </div>

      <div className="two-col">
        <Card>
          <h3 className="section-title" style={{ ["--dot" as string]: "var(--sec-dashboard)" }}>Account</h3>
          <dl className="kv">
            <dt>Name</dt><dd>{me.display_name}</dd>
            <dt>Username</dt><dd className="key">{me.username}</dd>
            <dt>Email</dt><dd>{me.email || <span className="muted">not set</span>}</dd>
            <dt>Access level</dt>
            <dd>{me.is_system_admin ? "System administrator" : "Standard user"}</dd>
          </dl>
        </Card>

        <Card>
          <h3 className="section-title" style={{ ["--dot" as string]: "var(--sec-plans)" }}>Project access</h3>
          {me.memberships.length === 0 ? (
            <p className="muted">
              You're not a member of any project yet. Browse projects and request access from the
              {" "}<Link to="/projects">Projects</Link> screen.
            </p>
          ) : (
            <ul className="plain-list">
              {me.memberships.map((m) => (
                <li key={m.project_id}>
                  <Link to={`/p/${m.project_key}/dashboard`}>
                    <strong className="key">{m.project_key}</strong>
                    <span className="muted"> — {projName(m.project_id)}</span>
                  </Link>
                  <span className="pill">{ROLE_LABEL[m.role] ?? m.role}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div ref={pwRef}>
        <ChangePasswordCard onChanged={refresh} />
      </div>
    </PlainShell>
  );
}

function ChangePasswordCard({ onChanged }: { onChanged: () => Promise<void> }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    if (next !== confirm) {
      setMsg({ kind: "err", text: "The new passwords do not match." });
      return;
    }
    setBusy(true);
    try {
      await http.post("/auth/password", { current_password: current, new_password: next });
      setMsg({ kind: "ok", text: "Password updated." });
      setCurrent(""); setNext(""); setConfirm("");
      await onChanged();
    } catch (err) {
      setMsg({ kind: "err", text: errText(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card style={{ marginTop: 16 }}>
      <h3 className="section-title" style={{ ["--dot" as string]: "var(--sec-traceability)" }}>Change password</h3>
      <form onSubmit={submit} className="stack" style={{ maxWidth: 420 }}>
        <Field label="Current password">
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label="New password (min 12 chars, mixed case + digit)">
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
        <Field label="Confirm new password">
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </Field>
        {msg && <div className={`notice ${msg.kind === "ok" ? "ok" : "err"}`}>{msg.text}</div>}
        <button className="primary" disabled={busy || !current || !next}>
          {busy ? "Updating…" : "Update password"}
        </button>
      </form>
    </Card>
  );
}
