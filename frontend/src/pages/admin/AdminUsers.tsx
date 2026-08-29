import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../api/client";
import type { InstanceUser, Project, UserMembership } from "../../api/types";
import { Badge, Dialog, Field, errText, useToast } from "../../ui";
import { Pager, SortHeader, sortBy, type SortState } from "../../components/table";
import { Icons } from "../../components/icons";

const PROJECT_ROLES = ["project_admin", "test_manager", "tester", "viewer"];

const PAGE = 25;

export function AdminUsers() {
  const qc = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [projectsFor, setProjectsFor] = useState<InstanceUser | null>(null);
  const [editFor, setEditFor] = useState<InstanceUser | null>(null);
  const [delFor, setDelFor] = useState<InstanceUser | null>(null);
  const [sort, setSort] = useState<SortState>({ field: "username", dir: "asc" });
  const [page, setPage] = useState(1);

  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => http.get<InstanceUser[]>("/users") });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin-users"] });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      http.put(`/users/${id}/status`, { status }),
    onSuccess: () => { invalidate(); toast("User updated"); },
    onError: (e) => toast(errText(e), "error"),
  });
  const reset = useMutation({
    mutationFn: (id: string) => http.post<{ temporary_password: string }>(`/users/${id}/password-reset`),
    onSuccess: (r) => setTempPassword(r.temporary_password),
    onError: (e) => toast(errText(e), "error"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => http.del(`/users/${id}`),
    onSuccess: () => { invalidate(); setDelFor(null); toast("User deleted"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const rows = sortBy(users.data ?? [], (u) => (u as unknown as Record<string, unknown>)[sort.field], sort.dir);
  const pageRows = rows.slice((page - 1) * PAGE, page * PAGE);

  return (
    <>
      <div className="page-header">
        <h2>Users</h2>
        <button className="primary" onClick={() => setCreating(true)}>+ New user</button>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <SortHeader label="Username" field="username" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} />
              <SortHeader label="Display name" field="display_name" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} />
              <SortHeader label="Email" field="email" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} />
              <SortHeader label="Role" field="is_system_admin" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />
              <SortHeader label="Status" field="status" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />
              <th className="nowrap">Actions</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((u) => (
              <tr key={u.id}>
                <td className="key">{u.username}</td>
                <td>{u.display_name}</td>
                <td>{u.email}</td>
                <td className="nowrap">{u.is_system_admin ? <Badge value="system admin" /> : <span className="muted">member</span>}</td>
                <td className="nowrap"><Badge value={u.status} /></td>
                <td className="nowrap">
                  <div className="inline-actions">
                    {!u.is_system_admin && (
                      <button className="sm" onClick={() => setProjectsFor(u)}>Projects</button>
                    )}
                    <button className="sm" onClick={() => reset.mutate(u.id)}>Reset password</button>
                    {u.status === "active" ? (
                      <button className="sm" onClick={() => setStatus.mutate({ id: u.id, status: "disabled" })}>Disable</button>
                    ) : (
                      <button className="sm" onClick={() => setStatus.mutate({ id: u.id, status: "active" })}>Enable</button>
                    )}
                    <button className="icon-btn" title="Edit user" onClick={() => setEditFor(u)}>{Icons.edit}</button>
                    {!u.is_system_admin && (
                      <button className="icon-btn warn" title="Delete user" onClick={() => setDelFor(u)}>{Icons.trash}</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} pages={Math.max(1, Math.ceil(rows.length / PAGE))} total={rows.length} pageSize={PAGE} onPage={setPage} />

      {creating && (
        <NewUserDialog onClose={() => setCreating(false)} onDone={() => { invalidate(); setCreating(false); }} />
      )}
      {projectsFor && (
        <ManageUserProjectsDialog user={projectsFor} onClose={() => setProjectsFor(null)} />
      )}
      {editFor && (
        <EditUserDialog user={editFor} onClose={() => setEditFor(null)}
          onDone={(msg) => { invalidate(); setEditFor(null); toast(msg); }} />
      )}
      {delFor && (
        <Dialog title="Delete user" onClose={() => setDelFor(null)}>
          <p>
            Delete <strong className="key">{delFor.username}</strong> ({delFor.display_name})? A user who
            belongs to a project or has authored content can’t be deleted — disable them instead.
          </p>
          <div className="inline-actions" style={{ marginTop: 14 }}>
            <button className="danger" disabled={remove.isPending} onClick={() => remove.mutate(delFor.id)}>Delete</button>
            <button onClick={() => setDelFor(null)}>Cancel</button>
          </div>
        </Dialog>
      )}
      {tempPassword && (
        <Dialog title="Temporary password" onClose={() => setTempPassword(null)}>
          <p className="muted">
            Hand this to the user. They sign in with it and are forced to set a new password immediately.
          </p>
          <pre style={{ background: "var(--surface-2)", padding: 12, borderRadius: 8, wordBreak: "break-all", whiteSpace: "pre-wrap", fontSize: 15 }}>
            {tempPassword}
          </pre>
        </Dialog>
      )}
    </>
  );
}

function EditUserDialog({ user, onClose, onDone }: { user: InstanceUser; onClose: () => void; onDone: (msg: string) => void }) {
  const toast = useToast();
  const [f, setF] = useState({ display_name: user.display_name, email: user.email, password: "" });
  const save = useMutation({
    mutationFn: () => {
      const body: Record<string, string> = {};
      if (f.display_name !== user.display_name) body.display_name = f.display_name;
      if (f.email !== user.email) body.email = f.email;
      if (f.password) body.password = f.password;
      return http.patch(`/users/${user.id}`, body);
    },
    onSuccess: () => onDone(f.password ? "User updated — new password set" : "User updated"),
    onError: (e) => toast(errText(e), "error"),
  });
  const dirty = f.display_name !== user.display_name || f.email !== user.email || f.password.length > 0;
  return (
    <Dialog title={`Edit ${user.username}`} onClose={onClose}>
      <Field label="Display name"><input value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} /></Field>
      <Field label="Email"><input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
      <Field label="Set a new password (optional, min 12 chars, mixed case + digit)">
        <input type="text" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} placeholder="leave blank to keep current" />
      </Field>
      <button className="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>Save changes</button>
    </Dialog>
  );
}

function ManageUserProjectsDialog({ user, onClose }: { user: InstanceUser; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [addPid, setAddPid] = useState("");
  const [addRole, setAddRole] = useState("tester");

  const memberships = useQuery({
    queryKey: ["user-memberships", user.id],
    queryFn: () => http.get<UserMembership[]>(`/users/${user.id}/memberships`),
  });
  const allProjects = useQuery({ queryKey: ["projects"], queryFn: () => http.get<Project[]>("/projects") });
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["user-memberships", user.id] });
    qc.invalidateQueries({ queryKey: ["admin-users"] });
  };

  const assign = useMutation({
    mutationFn: (v: { pid: string; role: string }) =>
      http.post(`/projects/${v.pid}/members`, { user_id: user.id, role: v.role }),
    onSuccess: () => { invalidate(); setAddPid(""); toast("Project assigned"); },
    onError: (e) => toast(errText(e), "error"),
  });
  const unassign = useMutation({
    mutationFn: (pid: string) => http.del(`/projects/${pid}/members/${user.id}`),
    onSuccess: () => { invalidate(); toast("Removed from project"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const memberPids = new Set((memberships.data ?? []).map((m) => m.project_id));
  const assignable = (allProjects.data ?? []).filter((p) => p.status === "active" && !memberPids.has(p.id));

  return (
    <Dialog title={`Projects — ${user.display_name}`} onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>
        Assign this user to projects and set the role they hold in each.
      </p>

      {(memberships.data ?? []).length === 0 ? (
        <p className="muted">Not a member of any project.</p>
      ) : (
        <table style={{ marginBottom: 14 }}>
          <thead><tr><th>Project</th><th>Role</th><th></th></tr></thead>
          <tbody>
            {memberships.data!.map((m) => (
              <tr key={m.project_id}>
                <td className="key">{m.project_key}</td>
                <td>
                  <select
                    value={m.role}
                    onChange={(e) => assign.mutate({ pid: m.project_id, role: e.target.value })}
                    style={{ width: "auto" }}
                  >
                    {PROJECT_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td className="nowrap">
                  <button className="sm" style={{ color: "var(--danger)" }} onClick={() => unassign.mutate(m.project_id)}>Remove</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Field label="Add to a project">
        <select value={addPid} onChange={(e) => setAddPid(e.target.value)}>
          <option value="">Select project…</option>
          {assignable.map((p) => <option key={p.id} value={p.id}>{p.key} — {p.name}</option>)}
        </select>
      </Field>
      <Field label="Role">
        <select value={addRole} onChange={(e) => setAddRole(e.target.value)}>
          {PROJECT_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </Field>
      <button className="primary" disabled={!addPid || assign.isPending} onClick={() => assign.mutate({ pid: addPid, role: addRole })}>
        Assign
      </button>
    </Dialog>
  );
}

function NewUserDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ username: "", email: "", display_name: "", password: "", is_system_admin: false });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF({ ...f, [k]: k === "is_system_admin" ? e.target.checked : e.target.value });
  const m = useMutation({
    mutationFn: () => http.post("/users", f),
    onSuccess: () => { toast("User created"); onDone(); },
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title="New user" onClose={onClose}>
      <Field label="Username"><input value={f.username} onChange={set("username")} autoFocus /></Field>
      <Field label="Email"><input type="email" value={f.email} onChange={set("email")} /></Field>
      <Field label="Display name"><input value={f.display_name} onChange={set("display_name")} /></Field>
      <Field label="Temporary password (min 12, mixed case + digit)">
        <input type="text" value={f.password} onChange={set("password")} />
      </Field>
      <label className="checkbox" style={{ marginBottom: 14 }}>
        <input type="checkbox" checked={f.is_system_admin} onChange={set("is_system_admin")} />
        System administrator
      </label>
      <button className="primary" disabled={m.isPending} onClick={() => m.mutate()}>Create user</button>
    </Dialog>
  );
}
