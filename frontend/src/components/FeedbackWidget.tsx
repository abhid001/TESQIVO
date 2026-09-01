import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { http } from "../api/client";
import { Dialog, Field, errText, useToast } from "../ui";

const CATEGORIES = [
  { value: "idea", label: "Idea / suggestion" },
  { value: "bug", label: "Something's broken" },
  { value: "question", label: "Question" },
  { value: "other", label: "Other" },
];

/** Always-available feedback button. Feedback goes straight to the administrators. */
export function FeedbackWidget({ projectId }: { projectId?: string }) {
  const loc = useLocation();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState("idea");
  const [message, setMessage] = useState("");

  const send = useMutation({
    mutationFn: () =>
      http.post("/feedback", {
        message,
        category,
        project_id: projectId ?? null,
        page_path: loc.pathname,
      }),
    onSuccess: () => {
      toast("Thanks — your feedback was sent to the administrators");
      setMessage("");
      setCategory("idea");
      setOpen(false);
    },
    onError: (e) => toast(errText(e), "error"),
  });

  return (
    <>
      <button className="feedback-fab" onClick={() => setOpen(true)} aria-label="Send feedback">
        <span aria-hidden>💬</span> Feedback
      </button>
      {open && (
        <Dialog title="Send feedback" onClose={() => setOpen(false)}>
          <p className="muted" style={{ marginTop: 0 }}>
            This goes directly to the people who run this TESQIVO instance.
          </p>
          <Field label="Type">
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Message">
            <textarea
              rows={5}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="What's on your mind?"
              autoFocus
            />
          </Field>
          <button
            className="primary"
            disabled={send.isPending || message.trim().length === 0}
            onClick={() => send.mutate()}
          >
            {send.isPending ? "Sending…" : "Send feedback"}
          </button>
        </Dialog>
      )}
    </>
  );
}
