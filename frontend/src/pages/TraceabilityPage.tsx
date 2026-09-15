import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Cycle, MatrixRow } from "../api/types";
import { Badge, EmptyState } from "../ui";

export function TraceabilityPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const [cycleId, setCycleId] = useState("");
  const [params] = useSearchParams();
  const focusKey = params.get("req");

  const cycles = useQuery({
    queryKey: ["cycles", pid],
    queryFn: () => http.get<Cycle[]>(`/projects/${pid}/cycles`),
    enabled: !!pid,
  });
  const matrix = useQuery({
    queryKey: ["matrix", pid, cycleId],
    queryFn: () =>
      http.get<{ rows: MatrixRow[] }>(
        `/projects/${pid}/traceability/matrix${cycleId ? `?cycle_id=${cycleId}` : ""}`,
      ),
    enabled: !!pid,
  });

  useEffect(() => {
    if (!focusKey || !matrix.data) return;
    document.getElementById(`req-row-${focusKey}`)?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [focusKey, matrix.data]);

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <div>
          <h2>Traceability</h2>
          <div className="page-sub">Requirement → test → result. Click a requirement to open it.</div>
        </div>
        <select value={cycleId} onChange={(e) => setCycleId(e.target.value)}>
          <option value="">Design view (no cycle)</option>
          {cycles.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.key} · {c.name}
            </option>
          ))}
        </select>
      </div>

      {matrix.data && matrix.data.rows.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Requirement</th>
                <th>Status</th>
                <th>Linked test cases</th>
                <th>Planned versions</th>
                <th>Latest results</th>
              </tr>
            </thead>
            <tbody>
              {matrix.data.rows.map((r) => (
                <tr key={r.requirement_key} id={`req-row-${r.requirement_key}`} className={r.requirement_key === focusKey ? "selected-row" : ""}>
                  <td className="key">
                    <Link to={`/p/${projectKey}/requirements?req=${encodeURIComponent(r.requirement_key)}`}>
                      {r.requirement_key}
                    </Link>
                    <div className="muted" style={{ whiteSpace: "normal" }}>
                      {r.requirement_title}
                    </div>
                  </td>
                  <td>
                    <Badge value={r.requirement_status} />
                  </td>
                  <td>{r.linked_test_case_keys.join(", ") || <span className="muted">—</span>}</td>
                  <td>{r.planned_version_labels.join(", ") || <span className="muted">—</span>}</td>
                  <td className="inline-actions">
                    {r.latest_results.length
                      ? r.latest_results.map((res, i) => <Badge key={i} value={res} />)
                      : <span className="muted">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState>No requirements yet. Add some in Requirements &amp; Defects.</EmptyState>
      )}
    </>
  );
}
