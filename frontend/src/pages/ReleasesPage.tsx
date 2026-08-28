import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Paginated, Release, ReleaseOverviewRow } from "../api/types";
import { Badge, Dialog, EmptyState, Field, errText, useToast } from "../ui";

const NEXT: Record<string, { to: string; label: string }[]> = {
  planned: [
    { to: "active", label: "Start release" },
    { to: "cancelled", label: "Cancel" },
  ],
  active: [
    { to: "released", label: "Mark released" },
    { to: "cancelled", label: "Cancel" },
  ],
  released: [{ to: "archived", label: "Archive" }],
  cancelled: [{ to: "archived", label: "Archive" }],
};

function fmtDate(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString() : "—";
}
function pct(v: number | null): string {
  return v === null ? "–" : `${(v * 100).toFixed(1)}%`;
}
function Bar({ value, accent }: { value: number | null; accent: string }) {
  return (
    <div className="mbar">
      {value !== null && <span style={{ width: `${Math.round(value * 100)}%`, background: accent }} />}
    </div>
  );
}

export function ReleasesPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{ mode: "create" } | { mode: "edit"; release: Release } | null>(null);

  const list = useQuery({
    queryKey: ["releases", pid],
    queryFn: () => http.get<Paginated<Release>>(`/projects/${pid}/releases?page_size=200`),
    enabled: !!pid,
  });
  const overview = useQuery({
    queryKey: ["release-overview", pid],
    queryFn: () => http.get<{ releases: ReleaseOverviewRow[] }>(`/projects/${pid}/reports/release-overview`),
    enabled: !!pid,
  });
  const ovById = Object.fromEntries((overview.data?.releases ?? []).map((r) => [r.release_id, r]));

  const refresh = () => {
    ["releases", "release-overview", "cycles", "summary", "cycle-breakdown"].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );
  };

  const transition = useMutation({
    mutationFn: ({ r, to }: { r: Release; to: string }) =>
      http.post(`/releases/${r.id}/transitions`, { to, expected_version: r.version }),
    onSuccess: () => {
      refresh();
      toast("Release updated");
    },
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;
  const releases = list.data?.items ?? [];

  return (
    <>
      <div className="page-header">
        <h2>Releases</h2>
        <button className="primary" onClick={() => setDialog({ mode: "create" })}>
          + New release
        </button>
      </div>

      {releases.length === 0 ? (
        <EmptyState>
          No releases yet. A release groups the plans, cycles, requirements and defects that ship together.
        </EmptyState>
      ) : (
        <div className="stack">
          {releases.map((r) => {
            const ov = ovById[r.id];
            const open = expanded === r.id;
            return (
              <div key={r.id} className="card release-card">
                <button className="release-head" onClick={() => setExpanded(open ? null : r.id)}>
                  <span className="key">{r.key}</span>
                  <span className="release-name">{r.name}</span>
                  {r.version_label && <span className="mtag">{r.version_label}</span>}
                  <Badge value={r.status} />
                  <span className="muted">
                    {fmtDate(r.start_date)} → {fmtDate(r.end_date)}
                  </span>
                  <span className="muted">{ov?.cycle_count ?? 0} cycles</span>
                  <span className="drill-hint" style={{ marginLeft: "auto" }}>{open ? "▾" : "▸"}</span>
                </button>

                <div className="release-progress">
                  <div>
                    <div className="cm-label">Completion</div>
                    <Bar value={ov?.completion ?? null} accent="var(--sec-repository)" />
                    <div className="cm-value">
                      {pct(ov?.completion ?? null)} · {ov?.terminal ?? 0}/{ov?.scoped_tests ?? 0}
                    </div>
                  </div>
                  <div>
                    <div className="cm-label">Pass rate</div>
                    <Bar value={ov?.pass_rate ?? null} accent={(ov?.pass_rate ?? 0) >= 0.8 ? "var(--success)" : "var(--sec-cycles)"} />
                    <div className="cm-value">{pct(ov?.pass_rate ?? null)}</div>
                  </div>
                  <div className="cm-counts">
                    <span className="badge">{ov?.requirements ?? 0} requirements</span>
                    <span className={`badge ${(ov?.open_critical_defects ?? 0) > 0 ? "FAILED" : ""}`}>
                      {ov?.open_critical_defects ?? 0} open critical
                    </span>
                  </div>
                </div>

                {open && (
                  <div className="release-detail">
                    <div className="inline-actions" style={{ marginBottom: 12 }}>
                      <button className="sm" onClick={() => setDialog({ mode: "edit", release: r })}>
                        Edit
                      </button>
                      {(NEXT[r.status] ?? []).map((t) => (
                        <button
                          key={t.to}
                          className="sm"
                          onClick={() => transition.mutate({ r, to: t.to })}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                    {r.description && <p className="muted">{r.description}</p>}

                    <div className="metric-sub-title">Test cycles in this release</div>
                    {ov && ov.cycles.length > 0 ? (
                      <div className="cycle-breakdown">
                        {ov.cycles.map((c) => (
                          <button
                            key={c.cycle_id}
                            className="cycle-row"
                            onClick={() => nav(`/p/${projectKey}/cycles`)}
                          >
                            <div className="cycle-row-head">
                              <span className="key">{c.cycle_key}</span>
                              <span className="cycle-name">{c.name}</span>
                              <span className="muted">{c.environment} / {c.build}</span>
                              <Badge value={c.status} />
                              <span className="drill-hint" style={{ marginLeft: "auto" }}>↗</span>
                            </div>
                            <div className="cycle-row-metrics">
                              <div>
                                <div className="cm-label">Completion</div>
                                <Bar value={c.completion} accent="var(--sec-repository)" />
                                <div className="cm-value">{pct(c.completion)} · {c.terminal}/{c.scoped}</div>
                              </div>
                              <div>
                                <div className="cm-label">Pass rate</div>
                                <Bar value={c.pass_rate} accent="var(--sec-cycles)" />
                                <div className="cm-value">{pct(c.pass_rate)}</div>
                              </div>
                              <div className="cm-counts">
                                <span className="badge PASSED">{c.passed} passed</span>
                                <span className="badge FAILED">{c.failed} failed</span>
                                <span className="badge BLOCKED">{c.blocked} blocked</span>
                                <span className="badge NOT_RUN">{c.not_run} not run</span>
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="muted">
                        No cycles yet. Create a plan for this release, then add cycles to it.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {dialog && pid && (
        <ReleaseDialog
          projectId={pid}
          release={dialog.mode === "edit" ? dialog.release : null}
          onClose={() => setDialog(null)}
          onDone={() => {
            refresh();
            setDialog(null);
          }}
        />
      )}
    </>
  );
}

function toDateInput(iso: string | null): string {
  return iso ? new Date(iso).toISOString().slice(0, 10) : "";
}

function ReleaseDialog({
  projectId,
  release,
  onClose,
  onDone,
}: {
  projectId: string;
  release: Release | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState({
    name: release?.name ?? "",
    version_label: release?.version_label ?? "",
    description: release?.description ?? "",
    start: toDateInput(release?.start_date ?? null),
    end: toDateInput(release?.end_date ?? null),
  });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setF({ ...f, [k]: e.target.value });

  const m = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {
        name: f.name,
        version_label: f.version_label || null,
        description: f.description || null,
      };
      if (f.start) body.start_date = new Date(f.start + "T00:00:00Z").toISOString();
      if (f.end) body.end_date = new Date(f.end + "T00:00:00Z").toISOString();
      if (release) {
        body.expected_version = release.version;
        if (!f.start) body.clear_start_date = true;
        if (!f.end) body.clear_end_date = true;
        return http.patch(`/releases/${release.id}`, body);
      }
      return http.post(`/projects/${projectId}/releases`, body);
    },
    onSuccess: onDone,
    onError: (e) => toast(errText(e), "error"),
  });

  return (
    <Dialog title={release ? `Edit ${release.key}` : "New release"} onClose={onClose}>
      <Field label="Name">
        <input value={f.name} onChange={set("name")} autoFocus />
      </Field>
      <Field label="Version label (optional)">
        <input value={f.version_label} onChange={set("version_label")} placeholder="v2026.03" />
      </Field>
      <div className="field-row">
        <Field label="Start date">
          <input type="date" value={f.start} onChange={set("start")} />
        </Field>
        <Field label="Target date">
          <input type="date" value={f.end} onChange={set("end")} />
        </Field>
      </div>
      <Field label="Description (optional)">
        <textarea value={f.description} onChange={set("description")} />
      </Field>
      <button className="primary" disabled={!f.name || m.isPending} onClick={() => m.mutate()}>
        {release ? "Save changes" : "Create release"}
      </button>
    </Dialog>
  );
}
