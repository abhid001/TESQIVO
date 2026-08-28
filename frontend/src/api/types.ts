export interface Me {
  id: string;
  username: string;
  display_name: string;
  is_system_admin: boolean;
  must_change_password: boolean;
  memberships: { project_id: string; project_key: string; role: string }[];
}

export interface Project {
  id: string;
  key: string;
  name: string;
  description: string | null;
  status: string;
  timezone: string;
  version: number;
}

export interface Step {
  action: string;
  expected_result: string;
  is_required: boolean;
}

export interface TestCase {
  id: string;
  key: string;
  project_id: string;
  folder_id: string | null;
  title: string;
  lifecycle_state: string;
  current_version_id: string | null;
  approved_version_id: string | null;
  has_draft_changes: boolean;
  automation_status: string;
  version: number;
}

export interface Version {
  id: string;
  version_number: number;
  status: string;
  title: string;
  description: string | null;
  preconditions: string | null;
  change_summary: string | null;
  steps: Step[];
}

export interface Plan {
  id: string;
  key: string;
  name: string;
  status: string;
  release_id: string | null;
  version: number;
}

export interface Cycle {
  id: string;
  key: string;
  plan_id: string;
  name: string;
  environment: string;
  build: string;
  release_id: string | null;
  status: string;
  version: number;
}

export interface CycleTestRow {
  id: string;
  test_case_id: string;
  test_case_key: string;
  test_case_title: string;
  test_case_version_id: string | null;
  assigned_to: string | null;
  displayed_result: string;
  authoritative_attempt_id: string | null;
  in_progress_attempt_id: string | null;
  attempt_count: number;
}

export interface CycleBreakdownRow {
  cycle_id: string;
  cycle_key: string;
  name: string;
  environment: string;
  build: string;
  status: string;
  scoped: number;
  terminal: number;
  passed: number;
  failed: number;
  blocked: number;
  not_run: number;
  completion: number | null;
  pass_rate: number | null;
}

export interface AttemptStep {
  order_index: number;
  action: string;
  expected_result: string;
  is_required: boolean;
  result: string;
  comment: string | null;
}

export interface Attempt {
  id: string;
  cycle_test_id: string;
  status: string;
  overall_result: string | null;
  result_overridden: boolean;
  environment: string;
  build: string;
  started_at: string;
  ended_at: string | null;
  steps: AttemptStep[];
  corrections: {
    field: string;
    old_value: string | null;
    new_value: string | null;
    reason: string;
    created_at: string;
  }[];
}

export interface Metric {
  metric_id: string;
  label: string;
  kind: "ratio" | "count";
  numerator: number | null;
  denominator: number | null;
  value: number | null;
  display: string;
  formula_version: number;
  data_as_of: string;
}

export interface ReportSummary {
  scope: Record<string, string | null>;
  formula_version: number;
  data_as_of: string;
  metrics: Metric[];
}

export interface Requirement {
  id: string;
  key: string;
  title: string;
  status: string;
  priority: string;
  req_type: string;
  release_id: string | null;
  version: number;
}

export interface Release {
  id: string;
  key: string;
  name: string;
  status: string;
  version_label: string | null;
  version: number;
}

export interface Defect {
  id: string;
  key: string;
  summary: string;
  status: string;
  severity: string;
  priority: string;
  release_id: string | null;
  version: number;
}

export interface MatrixRow {
  requirement_key: string;
  requirement_title: string;
  requirement_status: string;
  linked_test_case_keys: string[];
  planned_version_labels: string[];
  latest_results: string[];
}

export interface Paginated<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}
