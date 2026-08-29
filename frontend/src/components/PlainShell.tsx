import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "./Logo";
import { AppMenu } from "./AppMenu";
import { FeedbackWidget } from "./FeedbackWidget";

/** Chromed page frame for screens outside a project (projects list, profile,
 *  discover). Always offers a way home + the account menu, so nobody gets stuck. */
export function PlainShell({ children }: { children: ReactNode }) {
  const nav = useNavigate();
  return (
    <div className="app">
      <div className="appbar">
        <header className="topbar">
          <button className="brand brand-btn" onClick={() => nav("/")} aria-label="Home">
            <Logo size={26} />
            <span>TESQIVO</span>
          </button>
          <div className="spacer" />
          <AppMenu />
        </header>
      </div>
      <main className="main">{children}</main>
      <FeedbackWidget />
    </div>
  );
}
