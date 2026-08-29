import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../api/client";
import type { AccessRequest } from "../../api/types";
import { Badge, EmptyState, errText, useToast } from "../../ui";

const ROLES = ["tester", "test_manager", "viewer", "project_admin"];

export function AdminRequests() {
  const qc = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("pending");

  const q = useQuery({
    queryKey: ["access-requests", status],
    queryFn: () => http.get<AccessRequest[]>(`/access-requests?status=${status}`),
  });
  const decide = useMutation({
    mutationFn: (v: { id: string; approve: boolean; role?: string }) =>
      http.post(`/access-requests/${v.id}/decide`, { approve: v.approve, role: v.role }),
    onSuccess: (_d, v) => {
      qc.invalidateQueries({ queryKey: ["access-requests"] });
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast(v.approve ? "Access granted" : "Request denied");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  return (
    <>
      <div className="page-header">
        <h2>Access requests</h2>
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: "auto" }}>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="denied">Denied</option>
        </select>
      </div>

      {q.isLoading ? (
        <p>Loading…</p>
      ) : (q.data ?? []).length === 0 ? (
        <EmptyState>No {status} requests.</EmptyState>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>User</th><th>Project</th><th className="nowrap">Wants</th>
                <th>Note</th><th className="nowrap">Requested</th><th className="nowrap">Decision</th>
              </tr>
            </thead>
            <tbody>
              {q.data!.map((r) => <RequestRow key={r.id} r={r} onDecide={decide.mutate} pending={r.status === "pending"} />)}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function RequestRow({
  r, onDecide, pending,
}: {
  r: AccessRequest;
  onDecide: (v: { id: string; approve: boolean; role?: string }) => void;
  pending: boolean;
}) {
  const [role, setRole] = useState(r.requested_role);
  return (
    <tr>
      <td title={r.user_email}>{r.user_display_name}<div className="muted small key">{r.username}</div></td>
      <td className="key">{r.project_key}</td>
      <td className="nowrap">{r.requested_role}</td>
      <td>{r.message || <span className="muted">—</span>}</td>
      <td className="nowrap muted small">{new Date(r.created_at).toLocaleDateString()}</td>
      <td className="nowrap">
        {pending ? (
          <div className="inline-actions">
            <select value={role} onChange={(e) => setRole(e.target.value)} style={{ width: "auto" }}>
              {ROLES.map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
            <button className="sm primary" onClick={() => onDecide({ id: r.id, approve: true, role })}>Approve</button>
            <button className="sm" onClick={() => onDecide({ id: r.id, approve: false })}>Deny</button>
          </div>
        ) : (
          <Badge value={r.status} />
        )}
      </td>
    </tr>
  );
}
