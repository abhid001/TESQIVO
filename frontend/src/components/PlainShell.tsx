import type { ReactNode } from "react";
import { Topbar } from "./Topbar";
import { FeedbackWidget } from "./FeedbackWidget";

/** Chromed page frame for screens outside a project (projects list, profile).
 *  Always offers a way home + the account menu, so nobody gets stuck. */
export function PlainShell({ children }: { children: ReactNode }) {
  return (
    <div className="content">
      <Topbar brand />
      <main className="main">{children}</main>
      <FeedbackWidget />
    </div>
  );
}
