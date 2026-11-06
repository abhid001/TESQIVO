// PROPRIETARY - see ./LICENSE. Enterprise UI entry point, resolved as `@edition`
// only when the SPA is built with TESQIVO_EDITION=enterprise (vite.config.ts).
import { useState } from "react";
import type { EditionExtensions } from "../edition/types";
import { Icons } from "../components/icons";
import { AiDesignPage } from "./AiDesignPage";
import { GenerateDialog } from "./GenerateDialog";
import { GenerationReviewPage } from "./GenerationReviewPage";

function GenerateFromRequirements({ projectId, requirementIds, onDone }: {
  projectId: string; requirementIds: string[]; onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="sm" onClick={() => setOpen(true)} disabled={requirementIds.length > 10}
        title={requirementIds.length > 10 ? "Select at most 10 requirements" : "Generate test cases with AI"}>
        {Icons.sparkle} Generate tests
      </button>
      {open && (
        <GenerateDialog projectId={projectId} requirementIds={requirementIds}
          onClose={() => { setOpen(false); onDone(); }} />
      )}
    </>
  );
}

export const edition: EditionExtensions = {
  navItems: [{ to: "ai", label: "AI Test Design", section: "tests", icon: Icons.sparkle }],
  routes: [
    { path: "ai", element: <AiDesignPage /> },
    { path: "ai/:generationId", element: <GenerationReviewPage /> },
  ],
  RequirementsBulkAction: GenerateFromRequirements,
};
