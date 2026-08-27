"""The centralized controlled-field list (PRS §6.2, decision D-008).

A change to any controlled field on an Approved/Active test case forks a new Draft
version. Non-controlled organizational changes are audited but never version.
Changing this set is a code + migration change, never per-project config in Phase 1.
"""

from __future__ import annotations

# Version-scalar fields (on TestCaseVersion)
CONTROLLED_VERSION_FIELDS: frozenset[str] = frozenset(
    {"title", "description", "preconditions", "controlled_metadata"}
)

# Any change to the ordered step list (add / remove / reorder / edit action /
# edit expected_result / toggle is_required) is controlled.
CONTROLLED_STEP_CHANGE = "steps"

# Fields on the logical TestCase that are organizational only - audited, never versioned.
NON_CONTROLLED_LOGICAL_FIELDS: frozenset[str] = frozenset(
    {"folder_id", "title", "automation_status", "is_eligible_for_automation"}
)
# Note: logical `title` mirrors the current version title for listing convenience;
# edits always go through the version path which updates both.


def touches_controlled_content(
    *, changed_version_fields: set[str], steps_changed: bool
) -> bool:
    return steps_changed or bool(changed_version_fields & CONTROLLED_VERSION_FIELDS)
