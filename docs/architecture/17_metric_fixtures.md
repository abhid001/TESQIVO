# Metric Fixtures (Test-Fixture-Backed Formulas)

Required by PRS §22 and acceptance §19.5/§19.6. This is the canonical fixture the
`reporting` service integration tests assert against. `formula_version = 1`.

## Fixture A — "one covered release" (acceptance §19.5 primary)

Setup in project `DEMO`:

- Release `DEMO-REL-1` (Active).
- Requirements: `DEMO-REQ-1` (Active), `DEMO-REQ-2` (Active). Both linked → Release.
- Test cases: `DEMO-TC-1` (Active, approved v1), `DEMO-TC-2` (Active, approved v1).
  - `DEMO-REQ-1` → covers → `DEMO-TC-1`
  - `DEMO-REQ-2` → covers → `DEMO-TC-2`
- Plan `DEMO-PLAN-1` (Active, release = REL-1), scope = TC-1, TC-2.
- Cycle `DEMO-CYC-1` (Active, release REL-1, env `staging`, build `1001`).
  - Cycle Test for TC-1 (snapshot v1), Cycle Test for TC-2 (snapshot v1).
- Executions: TC-1 attempt → **PASSED**. TC-2 attempt → **FAILED**.
- Defect `DEMO-DEF-1`: severity **Critical**, status **Open**, linked from TC-2's
  attempt (`Execution Attempt → Defect`) and `Defect → Requirement DEMO-REQ-2`.

Scope for the report: project DEMO, release REL-1, cycle CYC-1, env staging, build 1001.

| Metric | Numerator / Denominator | Value |
|---|---|---|
| M-01 Scoped tests | 2 distinct cycle tests | **2** |
| M-02 Execution completion | 2 terminal / 2 scoped | **100.0%** |
| M-03 Pass rate | 1 passed / (1 passed + 1 failed + 0 blocked) | **50.0%** |
| M-04 Not-run count | 0 | **0** |
| M-05 Design coverage | 2 active reqs w/ qualifying linked TC / 2 active reqs | **100.0%** |
| M-06 Plan coverage | 2 active reqs w/ qualifying linked cycle test in scope / 2 | **100.0%** |
| M-07 Execution coverage | 2 active reqs w/ linked scoped cycle test w/ terminal attempt / 2 | **100.0%** |
| M-08 Pass coverage | see note below / reqs with ≥1 qualifying in-scope test (2) | **0.0%** |
| M-09 Requirements uncovered | active reqs with zero qualifying linked tests | **0** |
| M-10 Open critical defects | distinct Critical defects not Closed/Rejected | **1** |
| M-11 Defect-affected requirements | active reqs with direct or supported execution-mediated link to Open/In-Progress Critical/High defect (REQ-2 direct; REQ-2 also via TC-2→CT→attempt→DEF-1) | **1** |
| M-12 Automation coverage | automated active eligible / active eligible (both TCs eligible, none automated) | **0.0%** |
| M-13 Trace-link completeness | resolvable active links / active links (all resolvable) | **100.0%** |

Acceptance §19.5 asserts exactly: Design 100, Plan 100, Execution 100, Pass 0,
Requirements Uncovered 0, Open Critical Defects 1, Defect-Affected Requirements 1. ✔

### Decision D-017 — M-08 Pass Coverage interpretation

PRS §19.5 requires **Pass Coverage 0%** for a scope with "one passed test, one failed
test", while also requiring **Defect-Affected Requirements 1**. Under a purely
per-requirement reading of M-08 (`REQ-1→TC-1 passed` ⇒ REQ-1 counts) the fixture
yields 50%, not 0%; the only fixtures that yield 0% per-requirement force the failed
test to be linked to a requirement that is then *also* execution-mediated
defect-affected, making Defect-Affected Requirements 2. The two stated numbers are
only simultaneously satisfiable if **M-08 evaluates "every qualifying in-scope test
is Passed" across the whole selected scope** (PRS §9.1: *"Pass Coverage uses all
qualifying in-scope tests"*): a requirement earns pass coverage only when every
qualifying in-scope test it depends on passed **and nothing in the wider qualifying
in-scope set failed / was blocked / not run / in progress**. Implemented in
`app/domain/reporting.py::compute_all` (M-08) and asserted by
`tests/test_acceptance.py`.

## Fixture B — "half covered" (acceptance §19.5 secondary — verifies 50%)

Extend Fixture A with:

- `DEMO-REQ-3` (Active), linked → Release, **no** test case link.
- Nothing else.

Now, project/release scope (design view, no cycle filter):

| Metric | Value | Reason |
|---|---|---|
| M-05 Design coverage | **66.7%** | 2 of 3 active reqs covered |
| M-09 Requirements uncovered | **1** | REQ-3 |

And Fixture B' — a 2-requirement variant (REQ-1 covered+passed, REQ-4 uncovered) gives
Design/Plan/Execution **50.0%**, Pass coverage **50.0%** (1 of 2 reqs-with-a-test all
passed), Requirements Uncovered **1**. This is the "separate uncovered requirement
fixture verifies 50% coverage values" clause.

## Cross-surface equality test (acceptance §19.6)

For Fixture A's captured scope + `formula_version=1`:

```
assert dashboard_summary == api_reports_summary            # same envelope numbers
assert matrix_cell_counts == api_reports_summary            # per-requirement rows sum
assert csv_export_rows      == matrix_cell_counts           # byte-for-byte cell values
for metric in M01..M13:
    assert sum(len(drilldown(metric).rows_matching)) consistent with numerator/denominator
```

## Coverage-policy predicates encoded in SQL (PRS §9.1)

- Requirement in denominator ⇔ `status = 'active'`.
- Test qualifies for design coverage ⇔ selected/current version status ∈ {`approved`,`active`}.
- Draft / In Review / Deprecated / Archived tests → excluded.
- Skipped test → executed, not passed. Aborted → executed for exec-coverage, not passed.
- Empty denominator → `null` (API) / `–` (GUI).
- Date filters: project tz for boundaries, `[start, end)`, UTC storage.
- Percent: full precision compute, 1-decimal display.
