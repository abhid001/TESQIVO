// PROPRIETARY - see ./LICENSE. Shapes of the /ee/ai API.

export interface SuggestionPayload {
  title: string;
  objective: string;
  preconditions: string;
  steps: { action: string; expected_result: string }[];
  test_type: string;
  priority: string;
  automation_candidate: boolean;
  requirement_keys: string[];
  rationale: string;
}

export interface Suggestion {
  id: string;
  generation_id: string;
  ordinal: number;
  payload: SuggestionPayload;
  status: "pending" | "accepted" | "rejected";
  edited: boolean;
  possible_duplicate_of: string | null;
  reject_reason: string | null;
  test_case_id: string | null;
  test_case_key: string | null;
  version: number;
}

export interface Generation {
  id: string;
  project_id: string;
  status: "queued" | "running" | "completed" | "failed";
  sources: { type: "requirement" | "scenario"; id: string; key: string; title: string }[];
  story_text: string | null;
  options: { focus: string[]; max_cases: number; instructions: string };
  model: string | null;
  prompt_version: string;
  input_tokens: number;
  output_tokens: number;
  assumptions: string[];
  open_questions: string[];
  error_summary: string | null;
  created_at: string | null;
  finished_at: string | null;
  suggestions?: Suggestion[];
}

export interface GenerationOptions {
  focus_areas: { value: string; label: string }[];
  max_cases: number;
  max_requirements: number;
}
