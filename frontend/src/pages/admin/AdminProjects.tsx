import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../api/client";
import type { Project } from "../../api/types";
import { Badge, Dialog, Field, errText, useToast } from "../../ui";
import { SortHeader, sortBy, type SortState } from "../../components/table";

export function AdminProjects() {
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const [creating, setCreating] = useState(false);
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
    mutationFn: (p: Project) =>
      http.post(`/projects/${p.id}/archive`, { expected_version: p.version }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      toast("Project archived");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const rows = sortBy(projects.data ?? [], (p) => (p as unknown as Record<string, unknown>)[sort.field], sort.dir);

  return (
    <>
      <div className="page-header">
        <h2>Projects</h2>
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
                    <button className="sm" onClick={() => nav(`/p/${p.key}/dashboard`)}>Open</button>
                    {p.status === "active" && (
                      <button className="sm" onClick={() => archive.mutate(p)}>Archive</button>
                    )}
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
    </>
  );
}
