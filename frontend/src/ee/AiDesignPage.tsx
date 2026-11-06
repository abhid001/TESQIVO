// PROPRIETARY - see ./LICENSE.
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import { Badge, EmptyState } from "../ui";
import { Icons } from "../components/icons";
import { GenerateDialog } from "./GenerateDialog";
import type { Generation } from "./types";

/** /p/:key/ai - start a generation and revisit earlier ones. */
export function AiDesignPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const list = useQuery({
    queryKey: ["ai-generations", project?.id],
    queryFn: () => http.get<Generation[]>(`/ee/ai/projects/${project!.id}/generations`),
    enabled: !!project,
    refetchInterval: (q) => (q.state.data?.some((g) => g.status === "queued" || g.status === "running") ? 3000 : false),
  });

  if (!project) return <p>Loading…</p>;
  const rows = list.data ?? [];

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h2>AI Test Design</h2>
          <p className="muted" style={{ margin: 0 }}>
            Turn requirements, scenarios or user stories into suggested test cases, then review them.
          </p>
        </div>
        <span className="spacer-flex" />
        <button className="primary" onClick={() => setOpen(true)}>{Icons.sparkle} Generate test cases</button>
      </div>

      {list.isLoading ? <p>Loading…</p> : rows.length === 0 ? (
        <EmptyState>
          No generations yet. Click <strong>Generate test cases</strong>, or select requirements on the
          Requirements page and choose <strong>Generate tests</strong>.
        </EmptyState>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Started</th><th>Sources</th><th>Requested</th><th>Status</th></tr>
            </thead>
            <tbody>
              {rows.map((g) => (
                <tr key={g.id} className="clickable" onClick={() => nav(g.id)}>
                  <td>{g.created_at ? new Date(g.created_at).toLocaleString() : "-"}</td>
                  <td>
                    {g.sources.map((s) => s.key).join(", ") || (g.story_text ? "User story" : "-")}
                    {g.sources.length > 0 && g.story_text ? " + story" : ""}
                  </td>
                  <td>Up to {g.options.max_cases}</td>
                  <td><Badge value={g.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && <GenerateDialog projectId={project.id} onClose={() => setOpen(false)} />}
    </div>
  );
}
