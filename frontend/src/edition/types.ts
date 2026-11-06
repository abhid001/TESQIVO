import type { ComponentType, ReactElement, ReactNode } from "react";

/** Extension points the Enterprise UI (src/ee) can fill. Community code imports
 *  `@edition`, which Vite resolves to `src/edition/community.tsx` by default and to
 *  `src/ee/index.tsx` when built with TESQIVO_EDITION=enterprise (see vite.config.ts).
 *  Every slot is rendered only when the server says the feature is licensed. */
export interface EditionExtensions {
  /** Extra project sidebar tabs, e.g. { to: "ai", ... } -> /p/:key/ai */
  navItems: { to: string; label: string; section: string; icon: ReactNode }[];
  /** Extra routes inside the project shell (paths relative to /p/:key/). */
  routes: { path: string; element: ReactElement }[];
  /** Extra action in the Requirements selection bar. */
  RequirementsBulkAction: ComponentType<{ projectId: string; requirementIds: string[]; onDone: () => void }> | null;
}
