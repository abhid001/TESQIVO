# Artifact 12 — Reporting and Traceability Query Flow with Metric Versioning

**Question answered:** How does every surface (API, GUI, matrix, CSV) get identical
numbers, and how is a metric definition versioned? (PRS §9)

```mermaid
flowchart TB
    subgraph Consumers
        GUI[Dashboard widgets]
        MATRIX[Traceability matrix]
        CSVX[CSV export]
        APIX[GET /reports/*]
    end
    Consumers --> RS[Reporting Service - single entry point]
    RS --> SC[1. Resolve scope: project, release, plan, cycle, env, build, date range]
    SC --> FILT[2. Apply default exclusions: archived reqs/tests/releases/plans/cycles, removed links]
    FILT --> FV[3. Bind formula_version from metric_definition table]
    FV --> QRY[4. Execute the metric's parameterised SQL - one function per M-ID]
    QRY --> AA[uses authoritative-attempt CTE - PRS 7.5]
    QRY --> COV[uses coverage-policy predicates - PRS 9.1]
    QRY --> RESULT[5. Envelope:\nscope, filters, data_as_of, numerator, denominator,\nformula_version, refreshed_at, drilldown_token]
    RESULT --> Consumers
    RESULT --> DD[GET /reports/{metric}/drill-down?token -> exact contributing rows]
```

## Metric versioning

- Table `metric_definition (metric_id, formula_version, description, sql_ref, effective_from)`.
- Seeded by migration. A formula change = new migration adding a row with a bumped
  `formula_version`; old rows retained.
- Every response echoes the `formula_version` used. CSV filename embeds it.
- Reports/matrix/CSV requested with the same captured scope + `formula_version` must
  return identical numbers (acceptance §19.6). An integration test asserts this.

## `data_as_of` / freshness

Phase 1 computes metrics **on read** (no materialized cache). `data_as_of` = query start
timestamp = `refreshed_at`. Dashboards that exceed the 3s budget (PRS §15) return the
last computed snapshot with a visible "stale as of" marker; a background refresh job
recomputes. (Cache table `report_snapshot` is optional, added only if perf tests fail.)

## Empty-denominator handling

`denominator == 0` → API returns `value: null` (not `0`); GUI renders `–`; CSV writes
empty cell. Percentages: full precision internally, one decimal on display.

## Authoritative-attempt CTE (shared building block)

```sql
-- pseudo; real SQL in reporting/sql/authoritative_attempt.sql
WITH completed AS (
  SELECT a.*, c.new_value AS corrected_result, c.created_at AS corrected_at
  FROM execution_attempt a
  LEFT JOIN LATERAL (
     SELECT new_value, created_at FROM execution_correction
     WHERE attempt_id = a.id AND field = 'overall_result'
     ORDER BY created_at DESC LIMIT 1
  ) c ON true
  WHERE a.status IN ('PASSED','FAILED','BLOCKED','SKIPPED','ABORTED')
    AND a.cycle_id = :cycle_id AND a.environment = :env AND a.build = :build
),
ranked AS (
  SELECT *, row_number() OVER (
     PARTITION BY cycle_test_id
     ORDER BY COALESCE(corrected_at, ended_at) DESC, ended_at DESC, id DESC
  ) rn FROM completed
)
SELECT cycle_test_id,
       COALESCE(corrected_result, overall_result) AS effective_result
FROM ranked WHERE rn = 1;
```

See `17_metric_fixtures.md` for the worked M-01..M-13 fixture (acceptance §19.5).
