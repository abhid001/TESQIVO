import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProjects } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import type { DiscoverableProject } from "../api/types";
import { Card, Dialog, Field, EmptyState, errText, useToast } from "../ui";
import { PlainShell } from "../components/PlainShell";

const REQUEST_ROLES = [
  { value: "tester", label: "Tester — execute assigned work" },
  { value: "test_manager", label: "Test manager — full test management" },
  { value: "viewer", label: "Viewer — read only" },
];

export function ProjectPicker() {
  const { data, isLoading } = useProjects();
  const { me } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [form, setForm] = useState({ key: "", name: "" });

  const create = useMutation({
    mutationFn: () => http.post("/projects", form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      setCreating(false);
      setForm({ key: "", name: "" });
      toast("Project created");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const mine = data ?? [];
  const showBrowse = browsing || (!isLoading && mine.length === 0);

  return (
    <PlainShell>
      <div className="page-header">
        <h2>Projects</h2>
        <div className="inline-actions">
          <button onClick={() => setBrowsing((v) => !v)}>
            {showBrowse && browsing ? "Hide all projects" : "Browse all projects"}
          </button>
          {me?.is_system_admin && (
            <button className="primary" onClick={() => setCreating(true)}>+ New project</button>
          )}
        </div>
      </div>

      {isLoading ? (
        <p>Loading…</p>
      ) : mine.length > 0 ? (
        <div className="card-grid">
          {mine.map((p) => (
            <button key={p.id} className="project-card" onClick={() => nav(`/p/${p.key}/dashboard`)}>
              <strong className="key">{p.key}</strong>
              <span className="project-card-name">{p.name}</span>
            </button>
          ))}
        </div>
      ) : (
        <EmptyState>
          You're not in any project yet. Browse the list below and request access, or ask an
          administrator to add you.
        </EmptyState>
      )}

      {showBrowse && <DiscoverList onDone={() => qc.invalidateQueries({ queryKey: ["discoverable"] })} />}

      {creating && (
        <Dialog title="New project" onClose={() => setCreating(false)}>
          <Field label="Key (2–16 uppercase letters/digits)">
            <input value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value.toUpperCase() })} />
          </Field>
          <Field label="Name">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <button className="primary" onClick={() => create.mutate()} disabled={create.isPending || !form.key || !form.name}>
            Create
          </button>
        </Dialog>
      )}
    </PlainShell>
  );
}

function DiscoverList({ onDone }: { onDone: () => void }) {
  const toast = useToast();
  const nav = useNavigate();
  const [asking, setAsking] = useState<DiscoverableProject | null>(null);
  const list = useQuery({
    queryKey: ["discoverable"],
    queryFn: () => http.get<DiscoverableProject[]>("/projects/discoverable"),
  });

  return (
    <Card style={{ marginTop: 18 }}>
      <h3 className="section-title" style={{ ["--dot" as string]: "var(--sec-repository)" }}>All projects</h3>
      {list.isLoading ? (
        <p>Loading…</p>
      ) : (list.data ?? []).length === 0 ? (
        <p className="muted">No projects exist yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Key</th><th>Name</th><th className="nowrap">Access</th></tr>
            </thead>
            <tbody>
              {list.data!.map((p) => (
                <tr key={p.id}>
                  <td className="key">{p.key}</td>
                  <td>{p.name}{p.description && <div className="muted small">{p.description}</div>}</td>
                  <td className="nowrap">
                    {p.is_member ? (
                      <button className="sm" onClick={() => nav(`/p/${p.key}/dashboard`)}>Open</button>
                    ) : p.pending_request_role ? (
                      <span className="pill">Requested · {p.pending_request_role}</span>
                    ) : (
                      <button className="sm primary" onClick={() => setAsking(p)}>Request access</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {asking && (
        <RequestAccessDialog
          project={asking}
          onClose={() => setAsking(null)}
          onDone={() => { setAsking(null); list.refetch(); onDone(); toast("Access requested — an administrator will review it"); }}
        />
      )}
    </Card>
  );
}

function RequestAccessDialog({
  project, onClose, onDone,
}: { project: DiscoverableProject; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [role, setRole] = useState("tester");
  const [message, setMessage] = useState("");
  const m = useMutation({
    mutationFn: () =>
      http.post(`/projects/${project.id}/access-requests`, { requested_role: role, message }),
    onSuccess: onDone,
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title={`Request access — ${project.key}`} onClose={onClose}>
      <Field label="Role you need">
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {REQUEST_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </Field>
      <Field label="Note for the approver (optional)">
        <textarea rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />
      </Field>
      <button className="primary" disabled={m.isPending} onClick={() => m.mutate()}>
        {m.isPending ? "Sending…" : "Send request"}
      </button>
    </Dialog>
  );
}
