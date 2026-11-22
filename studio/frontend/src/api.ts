export type Workspace = { id: string; name: string; created_at: string };

export type ProviderKey = {
  id: string;
  name: string;
  base_url: string;
  model: string;
  key_hint: string;
  created_at: string;
};

export type RoleSummary = {
  role_id: string | null;
  name: string | null;
  role_type: string | null;
};

export type Team = {
  id: string;
  name: string;
  template_name: string | null;
  roles: RoleSummary[];
  created_at: string;
  updated_at: string;
};

export type TemplateInfo = {
  name: string;
  version: string;
  roles: { role_id: string; role_type: string }[];
};

export type ExpertOutcome = {
  role_id: string;
  status: string;
  sub_question: string;
  output: Record<string, unknown> | null;
  error: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  cached_prompt_tokens: number;
  skip_reason: string;
};

export type RunResult = {
  final_answer?: string;
  status?: string;
  error?: string | null;
  expert_outcomes?: ExpertOutcome[];
  verifier_verdict?: {
    passed: boolean;
    scores: Record<string, number>;
    comments: string;
    judge_role_id: string;
  } | null;
  usage_by_role?: {
    role_id: string;
    step: string;
    prompt_tokens: number;
    completion_tokens: number;
    cached_prompt_tokens: number;
    cache_scope: string;
  }[];
};

export type Run = {
  id: string;
  team_id: string;
  status: string;
  question: string;
  token_budget: number | null;
  trace_id: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  cached_prompt_tokens: number;
  cost_total: number;
  cost_baseline: number;
  cost_savings: number;
  error: string | null;
  result: RunResult | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type AuditEvent = {
  seq: number;
  event_type: string;
  ts: number;
  role_id: string | null;
  trace_id: string;
  payload: Record<string, unknown>;
};

export type AuditPage = {
  run_id: string;
  chain: { ok: boolean; checked: number; broken_at: number | null };
  events: AuditEvent[];
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function detailOf(data: unknown): string {
  if (!data || typeof data !== "object") return "请求失败";
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    return first.msg || "请求参数不正确";
  }
  return "请求失败";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const token = localStorage.getItem("studio_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const data = text ? (JSON.parse(text) as unknown) : null;
  if (!response.ok) {
    if (response.status === 401 && token) {
      localStorage.removeItem("studio_token");
      window.dispatchEvent(new Event("studio-unauthorized"));
    }
    throw new ApiError(response.status, detailOf(data));
  }
  return data as T;
}
