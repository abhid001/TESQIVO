// PROPRIETARY - see ./LICENSE.
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { http } from "../api/client";
import type { Paginated, Requirement, Scenario } from "../api/types";
import { Dialog, Field, errText, useToast } from "../ui";
import type { Generation, GenerationOptions } from "./types";

const DEFAULT_FOCUS = ["happy_path", "negative", "boundary"];

/** Ask the AI for test case suggestions. With `requirementIds` (from the
 *  Requirements selection bar) the sources are fixed; otherwise the user picks
 *  requirements / a scenario and can paste a user story. */
export function GenerateDialog({
  projectId,
  requirementIds,
  onClose,
}: {
  projectId: string;
  requirementIds?: string[];
  onClose: () => void;
}) {
  const { projectKey } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const fixed = !!requirementIds?.length;

  const [picked, setPicked] = useState<string[]>(requirementIds ?? []);
  const [filter, setFilter] = useState("");
  const [scenarioId, setScenarioId] = useState("");
  const [story, setStory] = useState("");
  const [focus, setFocus] = useState<string[]>(DEFAULT_FOCUS);
  const [maxCases, setMaxCases] = useState(8);
  const [instructions, setInstructions] = useState("");

  const options = useQuery({
    queryKey: ["ai-options"],
    queryFn: () => http.get<GenerationOptions>("/ee/ai/options"),
    staleTime: Infinity,
  });
  const reqs = useQuery({
    queryKey: ["requirements-all", projectId],
    queryFn: () => http.get<Paginated<Requirement>>(`/projects/${projectId}/requirements?page_size=200`),
    enabled: !fixed,
  });
  const scenarios = useQuery({
    queryKey: ["scenarios", projectId, ""],
    queryFn: () => http.get<{ items: Scenario[] }>(`/projects/${projectId}/scenarios`),
    enabled: !fixed,
  });

  const shown = useMemo(() => {
    const f = filter.trim().toLowerCase();
    const items = (reqs.data?.items ?? []).filter((r) => r.status !== "archived");
    return f ? items.filter((r) => `${r.key} ${r.title}`.toLowerCase().includes(f)) : items;
  }, [reqs.data, filter]);

  const maxReqs = options.data?.max_requirements ?? 10;
  const cap = options.data?.max_cases ?? 25;
  const hasSource = picked.length > 0 || !!scenarioId || story.trim().length > 0;

  const create = useMutation({
    mutationFn: () =>
      http.post<Generation>(`/ee/ai/projects/${projectId}/generations`, {
        requirement_ids: picked,
        scenario_id: scenarioId || null,
        story_text: story.trim() || null,
        focus,
        max_cases: maxCases,
        instructions: instructions.trim() || null,
      }),
    onSuccess: (g) => {
      toast("Generating test cases. This usually takes under a minute.");
      onClose();
      nav(`/p/${projectKey}/ai/${g.id}`);
    },
    onError: (e) => toast(errText(e), "error"),
  });

  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  return (
    <Dialog title="Generate test cases with AI" onClose={onClose}>
      {fixed ? (
        <p className="muted" style={{ marginTop: 0 }}>
          From {picked.length} selected requirement{picked.length === 1 ? "" : "s"}.
        </p>
      ) : (
        <>
          <Field label={`Requirements (up to ${maxReqs})`}>
            <input placeholder="Filter by key or title" value={filter} onChange={(e) => setFilter(e.target.value)} />
          </Field>
          <div className="stack" style={{ maxHeight: 180, overflowY: "auto", marginBottom: 12 }}>
            {shown.length === 0 && <span className="muted">No requirements match.</span>}
            {shown.map((r) => (
              <label key={r.id} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <input
                  type="checkbox"
                  checked={picked.includes(r.id)}
                  disabled={!picked.includes(r.id) && picked.length >= maxReqs}
                  onChange={() => setPicked(toggle(picked, r.id))}
                />
                <span><span className="mono">{r.key}</span> {r.title}</span>
              </label>
            ))}
          </div>
          <Field label="Scenario (optional)">
            <select value={scenarioId} onChange={(e) => setScenarioId(e.target.value)}>
              <option value="">None</option>
              {(scenarios.data?.items ?? []).filter((s) => s.status === "active").map((s) => (
                <option key={s.id} value={s.id}>{s.key} · {s.title}</option>
              ))}
            </select>
          </Field>
          <Field label="User story or feature description (optional)" hint="Paste a story, acceptance criteria or a feature spec.">
            <textarea rows={4} value={story} maxLength={12000} onChange={(e) => setStory(e.target.value)}
              placeholder="As a registered user, I want to reset my password by email so that…" />
          </Field>
        </>
      )}

      <span className="field-label">Cover</span>
      <div className="ai-focus-grid" style={{ margin: "6px 0 12px" }}>
        {(options.data?.focus_areas ?? []).map((f) => (
          <label key={f.value}>
            <input type="checkbox" checked={focus.includes(f.value)} onChange={() => setFocus(toggle(focus, f.value))} />
            <span>{f.label.charAt(0).toUpperCase() + f.label.slice(1)}</span>
          </label>
        ))}
      </div>

      <Field label="Maximum number of test cases">
        <input type="number" min={1} max={cap} value={maxCases}
          onChange={(e) => setMaxCases(Math.max(1, Math.min(cap, Number(e.target.value) || 1)))} />
      </Field>
      <Field label="Extra instructions (optional)" hint="For example: use the admin role, or focus on the mobile layout.">
        <textarea rows={2} value={instructions} maxLength={2000} onChange={(e) => setInstructions(e.target.value)} />
      </Field>

      <p className="notice info" style={{ fontSize: 12.5 }}>
        The selected content is sent to this instance's AI provider. You'll get suggestions to
        review first. Nothing is added to Test Cases until a test manager accepts it, and accepted
        tests start as Drafts.
      </p>
      <div className="inline-actions">
        <button className="primary" disabled={!hasSource || focus.length === 0 || create.isPending} onClick={() => create.mutate()}>
          {create.isPending ? "Starting…" : "Generate suggestions"}
        </button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}
