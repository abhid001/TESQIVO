import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../api/client";
import { useProject } from "../api/hooks";
import type { Defect, Paginated, Release, Requirement, TestCase } from "../api/types";
import { Badge, Card, Dialog, EmptyState, Field, errText, useToast } from "../ui";

export function BacklogPage() {
  const { projectKey } = useParams();
  const { project } = useProject(projectKey);
  const pid = project?.id;
  const qc = useQueryClient();
  const toast = useToast();
  const [dialog, setDialog] = useState<null | "requirement" | "release" | "defect" | "link">(null);

  const reqs = useQuery({
    queryKey: ["reqs", pid],
    queryFn: () => http.get<Paginated<Requirement>>(`/projects/${pid}/requirements`),
    enabled: !!pid,
  });
  const releases = useQuery({
    queryKey: ["releases", pid],
    queryFn: () => http.get<Paginated<Release>>(`/projects/${pid}/releases`),
    enabled: !!pid,
  });
  const defects = useQuery({
    queryKey: ["defects", pid],
    queryFn: () => http.get<Paginated<Defect>>(`/projects/${pid}/defects`),
    enabled: !!pid,
  });
  const cases = useQuery({
    queryKey: ["testcases-all", pid],
    queryFn: () => http.get<Paginated<TestCase>>(`/projects/${pid}/test-cases?page_size=200`),
    enabled: !!pid,
  });

  const invalidateAll = () =>
    ["reqs", "releases", "defects", "matrix"].forEach((k) =>
      qc.invalidateQueries({ queryKey: [k] }),
    );

  const transition = useMutation({
    mutationFn: ({ kind, id, version, to }: { kind: string; id: string; version: number; to: string }) =>
      http.post(`/${kind}/${id}/transitions`, { to, expected_version: version }),
    onSuccess: invalidateAll,
    onError: (e) => toast(errText(e), "error"),
  });

  if (!project) return <p>Loading…</p>;

  return (
    <>
      <div className="page-header">
        <h2>Requirements &amp; Defects</h2>
        <div className="inline-actions">
          <button onClick={() => setDialog("requirement")}>New requirement</button>
          <button onClick={() => setDialog("release")}>New release</button>
          <button onClick={() => setDialog("defect")}>New defect</button>
          <button className="primary" onClick={() => setDialog("link")}>
            Link requirement → test case
          </button>
        </div>
      </div>

      <div className="grid cols-2">
        <Card>
          <h3 style={{ marginTop: 0 }}>Requirements</h3>
          {reqs.data?.items.length ? (
            <table>
              <tbody>
                {reqs.data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="key">{r.key}</td>
                    <td>{r.title}</td>
                    <td>
                      <Badge value={r.status} />
                    </td>
                    <td>
                      {r.status === "draft" && (
                        <button
                          onClick={() =>
                            transition.mutate({
                              kind: "requirements",
                              id: r.id,
                              version: r.version,
                              to: "active",
                            })
                          }
                        >
                          Activate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState>None</EmptyState>
          )}
        </Card>

        <Card>
          <h3 style={{ marginTop: 0 }}>Releases</h3>
          {releases.data?.items.length ? (
            <table>
              <tbody>
                {releases.data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="key">{r.key}</td>
                    <td>{r.name}</td>
                    <td>
                      <Badge value={r.status} />
                    </td>
                    <td>
                      {r.status === "planned" && (
                        <button
                          onClick={() =>
                            transition.mutate({
                              kind: "releases",
                              id: r.id,
                              version: r.version,
                              to: "active",
                            })
                          }
                        >
                          Activate
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState>None</EmptyState>
          )}
        </Card>

        <Card>
          <h3 style={{ marginTop: 0 }}>Defects</h3>
          {defects.data?.items.length ? (
            <table>
              <tbody>
                {defects.data.items.map((d) => (
                  <tr key={d.id}>
                    <td className="key">{d.key}</td>
                    <td>{d.summary}</td>
                    <td>
                      <Badge value={d.severity} />
                    </td>
                    <td>
                      <Badge value={d.status} />
                    </td>
                    <td>
                      {d.status === "new" && (
                        <button
                          onClick={() =>
                            transition.mutate({
                              kind: "defects",
                              id: d.id,
                              version: d.version,
                              to: "open",
                            })
                          }
                        >
                          Open
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState>None</EmptyState>
          )}
        </Card>
      </div>

      {dialog && dialog !== "link" && (
        <CreateDialog
          kind={dialog}
          projectId={pid!}
          releases={releases.data?.items ?? []}
          onClose={() => setDialog(null)}
          onDone={() => {
            invalidateAll();
            setDialog(null);
          }}
        />
      )}
      {dialog === "link" && (
        <LinkDialog
          projectId={pid!}
          requirements={reqs.data?.items ?? []}
          testCases={cases.data?.items ?? []}
          onClose={() => setDialog(null)}
          onDone={() => {
            qc.invalidateQueries({ queryKey: ["matrix"] });
            setDialog(null);
          }}
        />
      )}
    </>
  );
}

function CreateDialog({
  kind,
  projectId,
  releases,
  onClose,
  onDone,
}: {
  kind: "requirement" | "release" | "defect";
  projectId: string;
  releases: Release[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [f, setF] = useState<Record<string, string>>({ severity: "major" });
  const path =
    kind === "requirement"
      ? `/projects/${projectId}/requirements`
      : kind === "release"
        ? `/projects/${projectId}/releases`
        : `/projects/${projectId}/defects`;
  const m = useMutation({
    mutationFn: () =>
      http.post(path, {
        title: f.title,
        name: f.name,
        summary: f.summary,
        severity: f.severity,
        release_id: f.release_id || null,
      }),
    onSuccess: onDone,
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title={`New ${kind}`} onClose={onClose}>
      {kind === "requirement" && (
        <Field label="Title">
          <input onChange={(e) => setF({ ...f, title: e.target.value })} />
        </Field>
      )}
      {kind === "release" && (
        <Field label="Name">
          <input onChange={(e) => setF({ ...f, name: e.target.value })} />
        </Field>
      )}
      {kind === "defect" && (
        <>
          <Field label="Summary">
            <input onChange={(e) => setF({ ...f, summary: e.target.value })} />
          </Field>
          <Field label="Severity">
            <select value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}>
              {["critical", "high", "major", "minor", "trivial"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </Field>
        </>
      )}
      {kind !== "release" && (
        <Field label="Release (optional)">
          <select onChange={(e) => setF({ ...f, release_id: e.target.value })}>
            <option value="">none</option>
            {releases.map((r) => (
              <option key={r.id} value={r.id}>
                {r.key} — {r.name}
              </option>
            ))}
          </select>
        </Field>
      )}
      <button className="primary" onClick={() => m.mutate()} disabled={m.isPending}>
        Create
      </button>
    </Dialog>
  );
}

function LinkDialog({
  projectId,
  requirements,
  testCases,
  onClose,
  onDone,
}: {
  projectId: string;
  requirements: Requirement[];
  testCases: TestCase[];
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [req, setReq] = useState("");
  const [tc, setTc] = useState("");
  const m = useMutation({
    mutationFn: () =>
      http.post(`/projects/${projectId}/trace-links`, {
        source_type: "requirement",
        source_id: req,
        target_type: "test_case",
        target_id: tc,
      }),
    onSuccess: () => {
      toast("Linked");
      onDone();
    },
    onError: (e) => toast(errText(e), "error"),
  });
  return (
    <Dialog title="Link requirement → test case" onClose={onClose}>
      <Field label="Requirement">
        <select value={req} onChange={(e) => setReq(e.target.value)}>
          <option value="">Select…</option>
          {requirements.map((r) => (
            <option key={r.id} value={r.id}>
              {r.key} — {r.title}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Test case">
        <select value={tc} onChange={(e) => setTc(e.target.value)}>
          <option value="">Select…</option>
          {testCases.map((t) => (
            <option key={t.id} value={t.id}>
              {t.key} — {t.title}
            </option>
          ))}
        </select>
      </Field>
      <button className="primary" disabled={!req || !tc} onClick={() => m.mutate()}>
        Create link
      </button>
    </Dialog>
  );
}
