export interface Me {
  id: string;
  username: string;
  display_name: string;
  email: string;
  is_system_admin: boolean;
  must_change_password: boolean;
  memberships: { project_id: string; project_key: string; role: string }[];
}

export interface DiscoverableProject {
  id: string;
  key: string;
  name: string;
  description: string | null;
  is_member: boolean;
  pending_request_role: string | null;
}

export interface AccessRequest {
  id: string;
  project_id: string;
  project_key: string;
  project_name: string;
  user_id: string;
  username: string;
  user_email: string;
  user_display_name: string;
  requested_role: string;
  message: string | null;
  status: string;
  created_at: string;
  decided_at: string | null;
}

export interface Feedback {
  id: string;
  category: string;
  message: string;
  page_path: string | null;
  status: string;
  admin_note: string | null;
  created_at: string;
  resolved_at: string | null;
  user_username: string;
  user_email: string;
  user_display_name: string;
  project_key: string | null;
  project_id: string | null;
}

export interface UserMembership {
  project_id: string;
  project_key: string;
  project_name: string;
  role: string;
}

export interface ReferenceValue {
  id: string;
  kind: string;
  value: string;
  is_active: boolean;
}

export interface ActivityItem {
  id: string;
  action: string;
  text: string;
  actor: string;
  kind: "ok" | "bad" | "info";
  at: string;
}

export interface AuditLogRow extends ActivityItem {
  actor_username: string | null;
  entity_type: string;
  entity_key: string | null;
  source: string;
}

export interface Notification {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  created_at: string;
  read: boolean;
}

export interface TrendPoint {
  date: string;
  passed: number;
  failed: number;
  blocked: number;
  other: number;
  total: number;
}

export interface InstanceUser {
  id: string;
  username: string;
  email: string;
  display_name: string;
  is_system_admin: boolean;
  status: string;
}

export interface Member {
  user_id: string;
  username: string;
  display_name: string;
  role: string;
  status: string;
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

export interface Scenario {
  id: string;
  key: string;
  title: string;
  description: string | null;
  status: string;
  requirement_id: string | null;
  test_count: number;
  version: number;
}

export interface TestCase {
  id: string;
  key: string;
  project_id: string;
  folder_id: string | null;
  scenario_id: string | null;
  plan_keys: string[];
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

export interface RequirementTraceSummary {
  test_cases: number;
  executions: number;
  defects: number;
}

export interface Requirement {
  id: string;
  key: string;
  title: string;
  description: string | null;
  acceptance_criteria: string | null;
  status: string;
  priority: string;
  req_type: string;
  component: string | null;
  labels: string | null;
  owner_id: string | null;
  owner_name: string | null;
  source_type: string;
  external_reference: string | null;
  release_id: string | null;
  release_key: string | null;
  release_name: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  linked_test_count: number;
  qualifying_test_count: number;
  trace_summary?: RequirementTraceSummary;
}

export interface Release {
  id: string;
  key: string;
  name: string;
  status: string;
  description: string | null;
  version_label: string | null;
  start_date: string | null;
  end_date: string | null;
  version: number;
}

export interface CoverageByType {
  tests: {
    automated: number;
    manual: number;
    not_applicable: number;
    total: number;
    automation_ratio: number | null;
  };
  requirement_coverage: {
    active_requirements: number;
    covered_by_automated: number;
    covered_by_manual: number;
    automated_ratio: number | null;
    manual_ratio: number | null;
  };
}

export interface ReleaseOverviewRow {
  release_id: string;
  release_key: string;
  name: string;
  status: string;
  version_label: string | null;
  start_date: string | null;
  end_date: string | null;
  cycle_count: number;
  cycles: CycleBreakdownRow[];
  scoped_tests: number;
  terminal: number;
  passed: number;
  failed: number;
  blocked: number;
  completion: number | null;
  pass_rate: number | null;
  requirements: number;
  open_critical_defects: number;
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

export interface TraceLink {
  id: string;
  source_type: string;
  source_id: string;
  target_type: string;
  target_id: string;
  relationship_type: string;
  origin: string;
  removed: boolean;
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
  pages?: number;
}
