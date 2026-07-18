export type Tenant = {
  tenant_id: string;
  name: string;
  plivo_numbers: string[];
  hms_base_url: string;
  hms_subdomain: string;
  ai_provider: string;
  voice_name: string;
  prompt_version: string;
  transfer_number: string | null;
  hospital_blurb: string | null;
  enabled: boolean;
  has_hms_token: boolean;
  has_gemini_key: boolean;
  created_at: string;
  updated_at: string;
};

export type TenantPayload = {
  tenant_id: string;
  name: string;
  plivo_numbers: string[];
  hms_base_url: string;
  hms_subdomain: string;
  hms_auth_token?: string;
  ai_provider?: string;
  gemini_api_key?: string | null;
  voice_name?: string;
  prompt_version?: string;
  transfer_number?: string | null;
  hospital_blurb?: string | null;
  enabled?: boolean;
};

export type CallLog = {
  session_id: string;
  tenant_id: string;
  call_id: string | null;
  direction: string;
  from_number: string | null;
  to_number: string | null;
  language: string | null;
  status: string;
  end_reason: string | null;
  interruption_count: number;
  tool_call_count: number;
  duration_seconds: number | null;
  error_message: string | null;
  started_at: string;
  ended_at: string | null;
};

const KEY = "healeka_voice_admin_key";
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function getAdminKey(): string | null {
  return sessionStorage.getItem(KEY);
}

export function setAdminKey(key: string) {
  sessionStorage.setItem(KEY, key);
}

export function clearAdminKey() {
  sessionStorage.removeItem(KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const key = getAdminKey();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (key) headers.set("X-Admin-Api-Key", key);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    clearAdminKey();
    throw new Error("Unauthorized — check admin API key");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: { detail?: string; message?: string } | null = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const detail =
      (typeof data?.detail === "string" && data.detail) ||
      data?.message ||
      text?.slice(0, 200) ||
      res.statusText;
    if (res.status === 500 || res.status === 502 || res.status === 504) {
      throw new Error(
        `${detail} — Is the API up? Dev proxy target is set via VITE_PROXY_TARGET ` +
          `(default http://127.0.0.1:8080).`,
      );
    }
    throw new Error(detail);
  }
  return data as T;
}

export const api = {
  listTenants: () => request<Tenant[]>("/admin/tenants"),
  getTenant: (id: string) => request<Tenant>(`/admin/tenants/${id}`),
  createTenant: (body: TenantPayload) =>
    request<Tenant>("/admin/tenants", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateTenant: (id: string, body: Partial<TenantPayload>) =>
    request<Tenant>(`/admin/tenants/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteTenant: (id: string) =>
    request<void>(`/admin/tenants/${id}`, { method: "DELETE" }),
  listCallLogs: (tenantId?: string) => {
    const q = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}&limit=50` : "?limit=50";
    return request<CallLog[]>(`/admin/call-logs${q}`);
  },
  health: () => request<{ status: string }>("/health"),
};
