import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Paginated, TestCase } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";
import { StepEditor, type DraftStep } from "../components/StepEditor";

export function RepositoryPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [creating, setCreating] = useState(false);

  const list = useQuery({
    queryKey: ["testcases", pid, q, state],
    queryFn: () =>
      http.get<Paginated<TestCase>>(
        `/projects/${pid}/test-cases?` +
          new URLSearchParams({ ...(q ? { q } : {}), ...(state ? { state } : {}) }).toString(),
      ),
    enabled: !!pid,
  });

  const [form, setForm] = useState<{ title: string; description: string; steps: DraftStep[] }>({
    title: "",
    description: "",
    steps: [{ action: "", expected_result: "", is_required: true }],
  });

  const create = useMutation({
    mutationFn: () =>
      http.post(`/projects/${pid}/test-cases`, {
        title: form.title,
        description: form.description,
        steps: form.steps.filter((s) => s.action && s.expected_result),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["testcases"] });
      setCreating(false);
      setForm({ title: "", description: "", steps: [{ action: "", expected_result: "", is_required: true }] });
      toast("Test case created");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <h2>Repository</h2>
        <button className="primary" onClick={() => setCreating(true)}>
          New test case
        </button>
      </div>

      <div className="toolbar">
        <input placeholder="Search title or key…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={state} onChange={(e) => setState(e.target.value)}>
          <option value="">Any state</option>
          {["draft", "in_review", "approved", "active", "deprecated", "archived"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>

      {list.isLoading ? (
        <p>Loading…</p>
      ) : list.data && list.data.items.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Key</th>
                <th>Title</th>
                <th>State</th>
                <th>Draft changes</th>
                <th>Automation</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((tc) => (
                <tr key={tc.id}>
                  <td className="key">
                    <Link to={`/p/${projectKey}/repository/${tc.id}`}>{tc.key}</Link>
                  </td>
                  <td>{tc.title}</td>
                  <td>
                    <Badge value={tc.lifecycle_state} />
                  </td>
                  <td>{tc.has_draft_changes ? "pending review" : "—"}</td>
                  <td>{tc.automation_status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState>No test cases match.</EmptyState>
      )}

      {creating && (
        <Dialog title="New test case" onClose={() => setCreating(false)}>
          <Field label="Title">
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </Field>
          <Field label="Description">
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </Field>
          <StepEditor steps={form.steps} onChange={(steps) => setForm({ ...form, steps })} />
          <button
            className="primary"
            style={{ marginTop: 12 }}
            disabled={!form.title || create.isPending}
            onClick={() => create.mutate()}
          >
            Create draft
          </button>
        </Dialog>
      )}
    </>
  );
}
