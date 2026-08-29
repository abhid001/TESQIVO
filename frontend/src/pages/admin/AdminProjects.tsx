import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../api/client";
import type { Project, ReferenceValue } from "../../api/types";
import { Badge, Dialog, Field, errText, useToast } from "../../ui";
import { SortHeader, sortBy, type SortState } from "../../components/table";
import { Icons } from "../../components/icons";

export function AdminProjects() {
  const qc = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [envFor, setEnvFor] = useState<Project | null>(null);
  const [editFor, setEditFor] = useState<Project | null>(null);
  const [delFor, setDelFor] = useState<Project | null>(null);
  const [form, setForm] = useState({ key: "", name: "" });
  const [sort, setSort] = useState<SortState>({ field: "key", dir: "asc" });

  const projects = useQuery({ queryKey: ["projects"], queryFn: () => http.get<Project[]>("/projects") });

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
  const archive = useMutation({
    mutationFn: (p: Project) => http.post(`/projects/${p.id}/archive`, { expected_version: p.version }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); toast("Project archived"); },
    onError: (e) => toast(errText(e), "error"),
  });
  const rename = useMutation({
    mutationFn: ({ p, name, description }: { p: Project; name: string; description: string }) =>
      http.patch(`/projects/${p.id}`, { expected_version: p.version, name, description }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); setEditFor(null); toast("Project updated"); },
    onError: (e) => toast(errText(e), "error"),
  });
  const remove = useMutation({
    mutationFn: (p: Project) => http.del(`/projects/${p.id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["projects"] }); setDelFor(null); toast("Project deleted"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const rows = sortBy(projects.data ?? [], (p) => (p as unknown as Record<string, unknown>)[sort.field], sort.dir);

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Projects</h2>
          <div className="page-sub">Create projects, manage environments, and archive</div>
        </div>
        <button className="primary" onClick={() => setCreating(true)}>+ New project</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <SortHeader label="Key" field="key" sort={sort} onSort={setSort} className="nowrap" />
              <SortHeader label="Name" field="name" sort={sort} onSort={setSort} />
              <SortHeader label="Status" field="status" sort={sort} onSort={setSort} className="nowrap" />
              <th className="nowrap">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <td className="key">{p.key}</td>
                <td>{p.name}</td>
                <td className="nowrap"><Badge value={p.status} /></td>
                <td className="nowrap">
                  <div className="inline-actions">
                    <button className="sm" onClick={() => setEnvFor(p)}>Environments</button>
                    {p.status === "active" && (
                      <button className="sm" onClick={() => archive.mutate(p)}>Archive</button>
                    )}
                    <button className="icon-btn" title="Edit project" onClick={() => setEditFor(p)}>{Icons.edit}</button>
                    <button className="icon-btn warn" title="Delete project" onClick={() => setDelFor(p)}>{Icons.trash}</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {creating && (
        <Dialog title="New project" onClose={() => setCreating(false)}>
          <Field label="Key (2–16 uppercase letters/digits)">
            <input value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value.toUpperCase() })} />
          </Field>
          <Field label="Name">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <button className="primary" disabled={!form.key || !form.name || create.isPending} onClick={() => create.mutate()}>
            Create
          </button>
        </Dialog>
      )}
      {envFor && <EnvironmentsDialog project={envFor} onClose={() => setEnvFor(null)} />}
      {editFor && (
        <EditProjectDialog project={editFor} busy={rename.isPending} onClose={() => setEditFor(null)}
          onSave={(name, description) => rename.mutate({ p: editFor, name, description })} />
      )}
      {delFor && (
        <Dialog title="Delete project" onClose={() => setDelFor(null)}>
          <p>
            Permanently delete <strong className="key">{delFor.key}</strong> — “{delFor.name}”?
            Only an <strong>archived</strong> project with no requirements, tests, plans, cycles,
            releases or defects can be deleted. This cannot be undone.
          </p>
          <div className="inline-actions" style={{ marginTop: 14 }}>
            <button className="danger" disabled={remove.isPending} onClick={() => remove.mutate(delFor)}>Delete project</button>
            <button onClick={() => setDelFor(null)}>Cancel</button>
          </div>
        </Dialog>
      )}
    </>
  );
}

function EditProjectDialog({ project, busy, onClose, onSave }: {
  project: Project; busy: boolean; onClose: () => void; onSave: (name: string, description: string) => void;
}) {
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  return (
    <Dialog title={`Edit ${project.key}`} onClose={onClose}>
      <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} autoFocus /></Field>
      <Field label="Description"><textarea value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
      <button className="primary" disabled={!name.trim() || busy} onClick={() => onSave(name, description)}>Save</button>
    </Dialog>
  );
}

function EnvironmentsDialog({ project, onClose }: { project: Project; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [value, setValue] = useState("");

  const refs = useQuery({
    queryKey: ["refs", project.id],
    queryFn: () => http.get<ReferenceValue[]>(`/projects/${project.id}/reference-values`),
  });
  const envs = (refs.data ?? []).filter((r) => r.kind === "environment");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["refs", project.id] });

  const add = useMutation({
    mutationFn: () => http.post(`/projects/${project.id}/reference-values`, { kind: "environment", value }),
    onSuccess: () => { invalidate(); setValue(""); toast("Environment added"); },
    onError: (e) => toast(errText(e), "error"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => http.del(`/projects/${project.id}/reference-values/${id}`),
    onSuccess: () => { invalidate(); toast("Environment removed"); },
    onError: (e) => toast(errText(e), "error"),
  });

  return (
    <Dialog title={`Environments — ${project.key}`} onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>
        These appear in the dashboard <strong>Environment</strong> filter and when creating cycles.
      </p>
      {envs.length === 0 ? (
        <p className="muted">No environments yet.</p>
      ) : (
        <ul className="plain-list" style={{ marginBottom: 12 }}>
          {envs.map((e) => (
            <li key={e.id}>
              <span style={{ flex: 1, textTransform: "capitalize" }}>{e.value}</span>
              <button className="sm" style={{ color: "var(--danger)" }} onClick={() => remove.mutate(e.id)}>Remove</button>
            </li>
          ))}
        </ul>
      )}
      <Field label="Add environment">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value.toLowerCase())}
          placeholder="e.g. pre-production"
          onKeyDown={(e) => e.key === "Enter" && value && add.mutate()}
        />
      </Field>
      <button className="primary" disabled={!value || add.isPending} onClick={() => add.mutate()}>Add</button>
    </Dialog>
  );
}
