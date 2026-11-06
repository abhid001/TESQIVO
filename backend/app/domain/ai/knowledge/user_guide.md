# TESQIVO user guide (assistant knowledge pack)

TESQIVO is a self-hosted test management tool. Teams write requirements, design
versioned test cases for them, plan and run test executions, log defects, and
report on coverage and release readiness. Everything is organised by **project**.

## Getting in

- **Sign in** with a username and password. "Forgot password?" on the sign-in
  screen sends a reset link by email only if the administrator configured email;
  otherwise it tells you to ask an administrator, who resets it from the Admin
  console.
- **Projects** (the first screen): open a project you belong to, or use
  **Request access** on another project and pick the role you need. A project
  admin approves or denies it in that project's Settings.
- **System administrators** work only in the **Admin** console (users, all
  projects, access requests, feedback). They do not enter the project screens.
- **Your profile** (top-right menu): account details, the projects you can
  access with your role in each, **Change password**, and **Sign out**.
- **Feedback** button (bottom-right): sends an idea, bug report or question
  straight to this instance's administrators.

Passwords must be at least 12 characters and include an upper-case letter, a
lower-case letter, a digit and a special character.

## Project navigation (left sidebar)

Overview, Requirements, Test Cases, Test Plans, Executions, Releases,
Traceability, Defects, Reports, plus **Logs** (project admins and test managers)
and **Settings** (project admins). The search box in the top bar jumps straight
to a record when you type its key (for example `DEMO-REQ-12`, `DEMO-TC-4`,
`DEMO-DEF-3`); any other text searches test cases.

Every record gets a readable key: `<PROJECT>-REQ-n` (requirement), `-TC-n` (test
case), `-SCN-n` (scenario), `-PLAN-n`, `-REL-n` (release), `-DEF-n` (defect).

## Overview (dashboard)

The "Quality Command Center" for the project. Tiles show Execution Progress,
Pass Rate, Requirements Coverage, Automation Coverage and Open Defects, with
charts for test status, execution trend, coverage by requirement priority, open
defects by severity, release readiness and traceability health, and a recent
activity feed. Filter it by release, cycle or environment. Clicking a metric
opens a drill-down list of the records behind the number.

## Requirements

What the product must do. Each requirement has a title, description,
acceptance criteria, type, priority, status (draft, active, fulfilled,
archived), owner, component, labels, release and an optional external
reference/link.

- Switch between list and grid view; filter by status, type and release.
- **Import** requirements from a CSV file; export all or the selected rows to CSV.
- **Link Tests** connects test cases to the selected requirements, which is what
  makes a requirement "covered". The Test Coverage column shows the state.
- Open a requirement to see its details, history and linked tests and defects,
  and jump to it in Traceability.
- Testers and test managers can create and edit requirements; only test
  managers can delete them.

## Test Cases

The test repository. A test case has a title, description, preconditions, an
ordered list of **steps** (each with an action and an expected result), an
automation status (not applicable, candidate, automated) and a lifecycle state.

**Lifecycle.** New test cases start as **Draft**. Then:

1. **Submit for review**. Needs a title and at least one step with both an
   action and an expected result.
2. In review, a test manager either clicks **Approve version** or **Request
   changes** (back to Draft).
3. **Activate** an approved test case so it can be added to new executions.
4. Later: **Deprecate** (kept but excluded from new selection), reinstate,
   **Archive**, or **Restore**.

**Versioning.** Editing the content (title, description, preconditions or
steps) of an approved or active test case creates a new Draft *version* and
leaves the previous approved version in use, so running executions are never
changed underneath you. The page shows that draft changes are waiting for
review. Moving the test to another folder or changing its automation status
does not create a version. Each test case page lists its full version history.

**Coverage.** Only approved and active test cases count towards requirement
coverage. Drafts, including AI-generated drafts, never do.

**Table tools.** Newest first, paginated. Change status or automation status
for one row in the table or for many selected rows at once. The Edit dialog can
also set the status and add the test case to a test plan.

**Scenarios** group the test cases that exercise one requirement
(Requirement → Scenario → Test case). Create one, optionally tied to a
requirement, then **Manage test cases** to assign tests to it.

Test managers author test cases and run the review workflow; testers run them.

## Test Plans

A plan defines *what* should be tested, for example for a release or a team.
Create one with **New plan**, then set its **Scope** (the test cases it
includes). Plans can be renamed or deleted.

## Executions (test cycles)

A cycle is one run of tests against a build and environment.

1. **New cycle**: pick the plan, a name, environment, build and optionally a
   release. It starts as a Draft.
2. **Manage tests** to choose which test cases are in the cycle.
3. **Activate**. At this moment TESQIVO takes a snapshot of each test's
   approved version, so later edits to the test case don't change what's being
   run. A test case needs an approved version to be included.
4. Run the tests in the **Execution Runner**: pick a cycle test, click **Start
   attempt**, then mark each step **Pass**, **Fail**, **Blocked** or **Skip**.
   The attempt's result is worked out from the steps: any failed required step
   means Failed; otherwise any blocked step means Blocked; all passed or
   skipped means Passed.
5. **Abort attempt** (a reason is required) stops an attempt without a result.
   **Start new attempt / retest** runs a test again; the latest completed
   attempt is the one that counts.
6. **Complete** the cycle when nothing is in progress. A test manager can
   **Reopen** it, with a reason. **Clone** makes a new draft copy of a cycle.

Completed attempts are never edited. A test manager can record a correction,
which is kept alongside the original result. Testers can run tests that are
assigned to them or unassigned.

## Releases

A release has a name, optional version label, start date and target date.
**Start release**, then **Mark released** when it ships, or **Archive** it. The
release view shows completion and pass rate across the test cycles in it.

## Traceability

The matrix that ties it all together: each requirement with its linked test
cases, the versions planned into executions, latest results and status. Use it
to spot uncovered requirements or failing coverage.

## Defects

Log a defect with **New defect**: summary, severity and optionally a release.
Testers and test managers create defects; only test managers delete them.

## Reports

Metrics grouped as Execution, Requirement coverage, and Quality &
traceability, filtered by release and cycle. Each row shows the value with its
numerator and denominator. **Export CSV** downloads the rows.

## Logs (project admins and test managers)

The project audit log: who did what and when (time, actor, action, record type,
key and source: web UI, API, import and so on). It can be filtered, for example
by a test case key.

## Settings (project admins)

Manage project members: **Add existing user**, or **Create new user** with a
temporary password (they must change it at first sign-in). Set or change each
member's role, remove members, and approve or deny access requests.

## Roles

- **Project admin**: project settings, members and roles, reference values,
  audit log.
- **Test manager**: test repository and its review workflow, plans, cycles,
  execution corrections, requirements, defects, traceability, audit log.
- **Tester**: runs assigned or unassigned tests, creates and edits
  requirements, defects and links. Testers don't author test cases.
- **Viewer**: read-only access to project data and reports.
- **System admin**: instance-wide users and projects, from the Admin console.

If something is greyed out or missing, it's usually the user's role. A project
admin can change it in Settings.

## AI features

- **Ask TESQIVO** (this assistant) explains the app. It can't see or change
  project data and only knows the page you're on and your role.
- **Generate test cases with AI** (Enterprise edition, when licensed and
  enabled): select requirements and generate suggested test cases. Testers and
  test managers can generate; a test manager reviews each suggestion and accepts
  or rejects it. Accepted suggestions become ordinary Draft test cases linked to
  their requirements and still go through the normal review and approval.
