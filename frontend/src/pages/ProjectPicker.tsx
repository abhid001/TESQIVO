import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProjects } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { Card, Dialog, Field, EmptyState, errText, useToast } from "../ui";
import { Logo } from "../components/Logo";

export function ProjectPicker() {
  const { data, isLoading } = useProjects();
  const { me } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ key: "", name: "" });

  const create = useMutation({
    mutationFn: () => http.post("/projects", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      setCreating(false);
      toast("Project created");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  return (
    <div className="auth-shell">
      <Card className="auth-card">
        <div className="brand-lockup" style={{ color: "var(--primary)" }}>
          <Logo size={28} />
          TESQIVO
        </div>
        <div className="page-header">
          <h2>Projects</h2>
          {me?.is_system_admin && (
            <button className="primary" onClick={() => setCreating(true)}>
              + New project
            </button>
          )}
        </div>
        {isLoading ? (
          <p>Loading…</p>
        ) : data && data.length > 0 ? (
          <div className="stack">
            {data.map((p) => (
              <button
                key={p.id}
                className="card"
                style={{ width: "100%", textAlign: "left", display: "block" }}
                onClick={() => nav(`/p/${p.key}/dashboard`)}
              >
                <strong className="key">{p.key}</strong>
                <span className="muted"> — {p.name}</span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState>No projects yet.</EmptyState>
        )}
      </Card>

      {creating && (
        <Dialog title="New project" onClose={() => setCreating(false)}>
          <Field label="Key (2–16 uppercase letters/digits)">
            <input
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value.toUpperCase() })}
            />
          </Field>
          <Field label="Name">
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <button className="primary" onClick={() => create.mutate()} disabled={create.isPending}>
            Create
          </button>
        </Dialog>
      )}
    </div>
  );
}
