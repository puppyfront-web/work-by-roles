export type Workspace = { id: string; name: string; created_at: string; role?: string };

export type User = { id: string; email: string; email_verified: boolean; created_at: string };

export type Member = { user_id: string; email: string; role: string; created_at: string };

export type Invite = {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  token?: string;
  invite_path?: string;
};

export type InvitePreview = { email: string; role: string; workspace_name: string; expires_at: string };

const ROLE_RANK: Record<string, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };

export function can(role: string | undefined, minimum: string): boolean {
  return (ROLE_RANK[role ?? ""] ?? -1) >= (ROLE_RANK[minimum] ?? 99);
}

export function roleLabel(role: string): string {
  if (role === "owner") return "所有者";
  if (role === "admin") return "管理员";
  if (role === "member") return "成员";
  if (role === "viewer") return "只读";
  return role;
}

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
  current_version: number;
  contracts?: Record<string, unknown>[];
  created_at: string;
  updated_at: string;
};

export type ContractVersion = {
  version: number;
  created_at: string;
  created_by: string | null;
  created_by_email: string | null;
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

export type SavingsLever = {
  id: string;
  tokens: number;
  cost: number;
  cached_tokens: number;
  roles: string[];
};

export type BudgetSkip = { role_id: string; step: string };

export type SavingsReceipt = {
  formula: string;
  live_run: boolean;
  baseline_tokens: number;
  actual_tokens: number;
  saved_tokens: number;
  baseline_cost: number;
  actual_cost: number;
  saved_cost: number;
  cached_prompt_tokens: number;
  levers: SavingsLever[];
  budget_skipped: BudgetSkip[];
  notes: string[];
};

export type UsageBucket = {
  prompt_tokens: number;
  completion_tokens: number;
  cached_prompt_tokens: number;
  cost_total: number;
  cache_hit_rate: number;
  saved_tokens?: number;
  saved_cost?: number;
  runs?: number;
};

export type UsageReport = {
  from: string;
  to: string;
  days: number;
  totals: UsageBucket;
  by_day: (UsageBucket & { day: string })[];
  by_model: (UsageBucket & { model: string })[];
  by_role: (UsageBucket & { role_id: string })[];
};

export type Run = {
  id: string;
  team_id: string;
  status: string;
  cancel_requested: boolean;
  model: string | null;
  contract_version: number | null;
  question: string;
  token_budget: number | null;
  trace_id: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  cached_prompt_tokens: number;
  cost_total: number;
  cost_baseline: number;
  cost_savings: number;
  savings: SavingsReceipt | null;
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

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const refresh = localStorage.getItem("studio_refresh");
  if (!refresh) return false;
  const response = await fetch("/api/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!response.ok) return false;
  const data = (await response.json()) as { access_token: string; refresh_token: string };
  localStorage.setItem("studio_token", data.access_token);
  localStorage.setItem("studio_refresh", data.refresh_token);
  return true;
}

export function saveSession(access: string, refresh: string) {
  localStorage.setItem("studio_token", access);
  localStorage.setItem("studio_refresh", refresh);
}

export function clearSession() {
  localStorage.removeItem("studio_token");
  localStorage.removeItem("studio_refresh");
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const token = localStorage.getItem("studio_token");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const data = text ? (JSON.parse(text) as unknown) : null;
  if (!response.ok) {
    if (response.status === 401 && token && retry && !path.startsWith("/api/auth/")) {
      refreshInFlight ??= refreshSession().finally(() => {
        refreshInFlight = null;
      });
      if (await refreshInFlight) return api<T>(path, init, false);
      clearSession();
      window.dispatchEvent(new Event("studio-unauthorized"));
    }
    throw new ApiError(response.status, detailOf(data));
  }
  return data as T;
}
