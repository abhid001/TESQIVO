import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../api/client";
import type { Feedback } from "../../api/types";
import { Badge, Dialog, Field, EmptyState, errText, useToast } from "../../ui";
import { Pager, SortHeader, sortBy, type SortState } from "../../components/table";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";
const PAGE = 20;
const STATUSES = ["open", "reviewing", "resolved"];

export function AdminFeedback() {
  const qc = useQueryClient();
  const toast = useToast();
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<SortState>({ field: "created_at", dir: "desc" });
  const [page, setPage] = useState(1);
  const [noteFor, setNoteFor] = useState<Feedback | null>(null);

  const q = useQuery({
    queryKey: ["feedback", filter],
    queryFn: () => http.get<Feedback[]>(`/feedback${filter ? `?status=${filter}` : ""}`),
  });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["feedback"] });

  const update = useMutation({
    mutationFn: (v: { id: string; status?: string; admin_note?: string }) =>
      http.patch(`/feedback/${v.id}`, { status: v.status, admin_note: v.admin_note }),
    onSuccess: () => { invalidate(); toast("Feedback updated"); },
    onError: (e) => toast(errText(e), "error"),
  });

  const rows = sortBy(q.data ?? [], (f) => (f as unknown as Record<string, unknown>)[sort.field], sort.dir);
  const pageRows = rows.slice((page - 1) * PAGE, page * PAGE);

  return (
    <>
      <div className="page-header">
        <h2>Feedback</h2>
        <div className="inline-actions">
          <select value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); }} style={{ width: "auto" }}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <a className="btn" href={`${API_BASE}/feedback/export?format=csv${filter ? `&status=${filter}` : ""}`}>Export CSV</a>
          <a className="btn" href={`${API_BASE}/feedback/export?format=txt${filter ? `&status=${filter}` : ""}`}>Export text</a>
        </div>
      </div>

      {q.isLoading ? (
        <p>Loading…</p>
      ) : rows.length === 0 ? (
        <EmptyState>No feedback yet.</EmptyState>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <SortHeader label="Received" field="created_at" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />
                  <SortHeader label="Type" field="category" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />
                  <SortHeader label="From" field="user_username" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />
                  <SortHeader label="Project" field="project_key" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />
                  <th>Message</th>
                  <SortHeader label="Status" field="status" sort={sort} onSort={(s) => { setSort(s); setPage(1); }} className="nowrap" />
                  <th className="nowrap">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.map((f) => (
                  <tr key={f.id}>
                    <td className="nowrap muted small">{new Date(f.created_at).toLocaleDateString()}</td>
                    <td className="nowrap"><Badge value={f.category} /></td>
                    <td className="nowrap" title={f.user_email}>{f.user_username}</td>
                    <td className="nowrap key">{f.project_key ?? "—"}</td>
                    <td>
                      <div className="clamp-2">{f.message}</div>
                      {f.page_path && <div className="muted small">{f.page_path}</div>}
                      {f.admin_note && <div className="note-line">Note: {f.admin_note}</div>}
                    </td>
                    <td className="nowrap"><Badge value={f.status} /></td>
                    <td className="nowrap">
                      <div className="inline-actions">
                        <select
                          value={f.status}
                          onChange={(e) => update.mutate({ id: f.id, status: e.target.value })}
                          style={{ width: "auto" }}
                        >
                          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                        <button className="sm" onClick={() => setNoteFor(f)}>Note</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pager page={page} pages={Math.max(1, Math.ceil(rows.length / PAGE))} total={rows.length} pageSize={PAGE} onPage={setPage} />
        </>
      )}

      {noteFor && (
        <NoteDialog
          feedback={noteFor}
          onClose={() => setNoteFor(null)}
          onSave={(note) => { update.mutate({ id: noteFor.id, admin_note: note }); setNoteFor(null); }}
        />
      )}
    </>
  );
}

function NoteDialog({ feedback, onClose, onSave }: { feedback: Feedback; onClose: () => void; onSave: (n: string) => void }) {
  const [note, setNote] = useState(feedback.admin_note ?? "");
  return (
    <Dialog title="Internal note" onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>“{feedback.message}”</p>
      <Field label="Note (visible to administrators only)">
        <textarea rows={4} value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
      </Field>
      <button className="primary" onClick={() => onSave(note)}>Save note</button>
    </Dialog>
  );
}
