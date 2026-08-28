import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import { useRole, canManageProject } from "../auth/AuthContext";
import type { InstanceUser, Member } from "../api/types";
import { Dialog, EmptyState, Field, errText, useToast } from "../ui";
import { SortHeader, sortBy, type SortState } from "../components/table";

const ROLES = [
  { value: "project_admin", label: "Project admin — settings & members" },
  { value: "test_manager", label: "Test manager — full test management" },
  { value: "tester", label: "Tester — execute assigned work" },
  { value: "viewer", label: "Viewer — read only" },
];

export function ProjectSettingsPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const role = useRole(pid);
  const qc = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [sort, setSort] = useState<SortState>({ field: "username", dir: "asc" });

  const members = useQuery({
    queryKey: ["members", pid],
    queryFn: () => http.get<Member[]>(`/projects/${pid}/members`),
    enabled: !!pid,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["members", pid] });

  const changeRole = useMutation({
    mutationFn: ({ user_id, role }: { user_id: string; role: string }) =>
      http.post(`/projects/${pid}/members`, { user_id, role }),
    onSuccess: () => { invalidate(); toast("Role updated"); },
    onError: (e) => toast(errText(e), "error"),
  });
  const remove = useMutation({
    mutationFn: (user_id: string) => http.del(`/projects/${pid}/members/${user_id}`),
    onSuccess: () => { invalidate(); toast("Member removed"); },
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;
  if (!canManageProject(role)) {
    return <EmptyState>Only a project administrator can manage members.</EmptyState>;
  }

  const rows = sortBy(members.data ?? [], (m) => (m as unknown as Record<string, unknown>)[sort.field], sort.dir);

  return (
    <>
      <div className="page-header">
        <h2>Project settings — members</h2>
        <button className="primary" onClick={() => setAdding(true)}>+ Add member</button>
      </div>

      <p className="muted">
        Members work in the test management tool for <strong>{project.key}</strong>. A
        <strong> Test manager</strong> can author test cases, manage plans, cycles and releases, and record
        executions. Administrator actions (instance users, all projects) live in the Admin console.
      </p>

      <div className="table-wrap" style={{ marginTop: 12 }}>
        <table>
          <thead>
            <tr>
              <SortHeader label="Username" field="username" sort={sort} onSort={setSort} />
              <SortHeader label="Role" field="role" sort={sort} onSort={setSort} className="nowrap" />
              <th className="nowrap">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.user_id}>
                <td className="key">{m.username}</td>
                <td className="nowrap">
                  <select
                    value={m.role}
                    onChange={(e) => changeRole.mutate({ user_id: m.user_id, role: e.target.value })}
                    style={{ width: "auto" }}
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>{r.value}</option>
                    ))}
                  </select>
                </td>
                <td className="nowrap">
                  <button className="sm" style={{ color: "var(--danger)" }} onClick={() => remove.mutate(m.user_id)}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {adding && pid && (
        <AddMemberDialog projectId={pid} onClose={() => setAdding(false)} onDone={() => { invalidate(); setAdding(false); }} />
      )}
    </>
  );
}

function AddMemberDialog({ projectId, onClose, onDone }: { projectId: string; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [mode, setMode] = useState<"existing" | "new">("new");
  const [role, setRole] = useState("test_manager");
  const [userId, setUserId] = useState("");
  const [nu, setNu] = useState({ username: "", email: "", display_name: "", password: "" });

  const users = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => http.get<InstanceUser[]>("/users"),
    enabled: mode === "existing",
  });

  const m = useMutation({
    mutationFn: () =>
      http.post(`/projects/${projectId}/members`, {
        role,
        ...(mode === "existing" ? { user_id: userId } : { new_user: nu }),
      }),
    onSuccess: () => { toast("Member added"); onDone(); },
    onError: (e) => toast(errText(e), "error"),
  });

  return (
    <Dialog title="Add member" onClose={onClose}>
      <div className="inline-actions" style={{ marginBottom: 14 }}>
        <button className={mode === "new" ? "primary" : ""} onClick={() => setMode("new")}>Create new user</button>
        <button className={mode === "existing" ? "primary" : ""} onClick={() => setMode("existing")}>Add existing user</button>
      </div>

      <Field label="Role in this project">
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {ROLES.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
      </Field>

      {mode === "existing" ? (
        <Field label="User">
          <select value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">Select…</option>
            {users.data?.filter((u) => u.status === "active").map((u) => (
              <option key={u.id} value={u.id}>{u.username} — {u.display_name}</option>
            ))}
          </select>
        </Field>
      ) : (
        <>
          <Field label="Username"><input value={nu.username} onChange={(e) => setNu({ ...nu, username: e.target.value })} /></Field>
          <Field label="Email"><input type="email" value={nu.email} onChange={(e) => setNu({ ...nu, email: e.target.value })} /></Field>
          <Field label="Display name"><input value={nu.display_name} onChange={(e) => setNu({ ...nu, display_name: e.target.value })} /></Field>
          <Field label="Temporary password (min 12, mixed case + digit)">
            <input type="text" value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })} />
          </Field>
        </>
      )}

      <button
        className="primary"
        disabled={m.isPending || (mode === "existing" ? !userId : !nu.username || !nu.email || nu.password.length < 12)}
        onClick={() => m.mutate()}
      >
        Add member
      </button>
    </Dialog>
  );
}
