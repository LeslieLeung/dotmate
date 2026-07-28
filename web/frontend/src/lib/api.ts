import { getToken, clearToken } from "./auth";

const API_BASE = "/api";

export class ApiError extends Error {
  fieldErrors: Record<string, string>;

  constructor(message: string, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.name = "ApiError";
    this.fieldErrors = fieldErrors;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      throw new ApiError(
        detail.message || `Request failed: ${res.status}`,
        detail.fields || {}
      );
    }
    if (Array.isArray(detail)) {
      const fields = Object.fromEntries(
        detail.map((item) => [
          Array.isArray(item.loc) ? String(item.loc.at(-1)) : "form",
          item.msg || "Invalid value",
        ])
      );
      throw new ApiError("Check the highlighted fields", fields);
    }
    throw new ApiError(detail || `Request failed: ${res.status}`);
  }

  if (res.status === 204) return undefined as T;

  return res.json();
}

// ── Types ────────────────────────────────────────────────

export interface Device {
  id: number;
  name: string;
  device_id: string;
  api_credential_id: number;
  api_credential_name: string;
  vendor: string;
  vendor_capabilities: string[];
  show_battery_icon: boolean;
  show_battery_percentage: boolean;
  show_refresh_time: boolean;
  remote_status: RemoteDeviceStatus | null;
  status_policy: DeviceStatusPolicy;
  schedules: Schedule[];
}

export interface RemoteDeviceStatus {
  remote_device_id: string;
  alias: string | null;
  location: string | null;
  version: string;
  current: string;
  description: string;
  battery: string;
  wifi: string;
  last_render: string;
  rotated: boolean;
  border: number;
  image_count: number;
  next_battery_render: string;
  next_power_render: string;
}

export interface DeviceStatusPolicy {
  refresh_interval_minutes: number | null;
  effective_interval_minutes: number | null;
  interval_source: string | null;
  state: "pending" | "refreshing" | "ready" | "stale" | "error";
  last_attempt_at: string | null;
  last_success_at: string | null;
  next_refresh_at: string | null;
  last_error: string | null;
  refresh_requested_at: string | null;
}

export interface DeviceStatusRefreshResponse {
  requested_at: string;
  queued: number;
}

export interface Schedule {
  id: number;
  name: string;
  cron: string | null;
  type: string;
  type_label: string;
  params: Record<string, unknown> | null;
  summary: ScheduleSummaryItem[];
}

export interface ScheduleSummaryItem {
  label: string;
  value: string;
}

export interface Settings {
  request_interval: number;
}

export interface Vendor {
  id: string;
  label: string;
  capabilities: string[];
}

export interface ApiCredential {
  id: number;
  name: string;
  vendor: string;
  masked_key: string;
  device_count: number;
}

export interface DeviceSyncStats {
  fetched: number;
  created: number;
  linked: number;
  duplicates: number;
}

export interface ApiCredentialBatchResult {
  index: number;
  name: string;
  vendor: string;
  status: "success" | "error";
  credential?: ApiCredential;
  sync?: DeviceSyncStats;
  error?: string;
}

export interface RemoteDeviceSettings {
  alias: string | null;
  location: string | null;
  timezone: string | null;
  power_interval_minutes: number | null;
  battery_interval_minutes: number | null;
  sleep: { enabled: boolean; start: string; end: string } | null;
}

export interface RemoteTimezone {
  key: string;
  name: string;
  utc_offset_minutes: number;
  utc_offset_label: string;
}

export interface RemoteContent {
  type: string;
  key: string | null;
  task_alias: string | number | null;
  refresh_now: boolean | null;
  title: string | null;
  message: string | null;
  signature: string | null;
  link: string | null;
  border: number | null;
  dither_type: string | null;
  dither_kernel: string | null;
  has_icon: boolean;
  has_image: boolean;
}

export interface ScheduleFieldOption {
  value: string | number | boolean;
  label: string;
}

export interface ScheduleFieldSchema {
  type: "string" | "integer" | "number" | "boolean" | "bytes" | "object";
  label: string;
  description?: string;
  required: boolean;
  input: "text" | "textarea" | "time" | "url" | "password" | "select";
  section: "main" | "display" | "advanced";
  sensitive: boolean;
  hidden: boolean;
  default?: unknown;
  options?: ScheduleFieldOption[];
}

export interface ScheduleTypeDefinition {
  label: string;
  description: string;
  fields: Record<string, ScheduleFieldSchema>;
}

export type ScheduleTypeSchema = Record<string, ScheduleTypeDefinition>;

export interface AuthStatus {
  auth_required: boolean;
  authenticated: boolean;
}

// ── Devices ──────────────────────────────────────────────

export const devicesApi = {
  list: () => request<Device[]>("/devices"),
  get: (id: number) => request<Device>(`/devices/${id}`),
  create: (data: {
    name: string;
    device_id: string;
    api_credential_id: number;
    show_battery_icon?: boolean;
    show_battery_percentage?: boolean;
    show_refresh_time?: boolean;
  }) => request<Device>("/devices", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<Device>) =>
    request<Device>(`/devices/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  delete: (id: number) => request<void>(`/devices/${id}`, { method: "DELETE" }),
  remoteSettings: (id: number) =>
    request<RemoteDeviceSettings>(`/devices/${id}/remote/settings`),
  updateRemoteSettings: (id: number, data: Partial<RemoteDeviceSettings>) =>
    request<RemoteDeviceSettings>(`/devices/${id}/remote/settings`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  remoteTimezones: (id: number) =>
    request<RemoteTimezone[]>(`/devices/${id}/remote/timezones`),
  nextContent: (id: number) =>
    request<{ message: string }>(`/devices/${id}/remote/next`, { method: "POST" }),
  remoteContent: (id: number, taskType = "loop") =>
    request<RemoteContent[]>(
      `/devices/${id}/remote/content?task_type=${encodeURIComponent(taskType)}`
    ),
  refreshStatus: (id: number) =>
    request<DeviceStatusRefreshResponse>(`/devices/${id}/remote/status/refresh`, {
      method: "POST",
    }),
  refreshAllStatuses: () =>
    request<DeviceStatusRefreshResponse>("/devices/remote/statuses/refresh", {
      method: "POST",
    }),
  updateStatusPolicy: (id: number, refreshIntervalMinutes: number | null) =>
    request<DeviceStatusPolicy>(`/devices/${id}/remote/status/policy`, {
      method: "PATCH",
      body: JSON.stringify({ refresh_interval_minutes: refreshIntervalMinutes }),
    }),
};

export const vendorsApi = {
  list: () => request<Vendor[]>("/vendors"),
};

export const apiKeysApi = {
  list: () => request<ApiCredential[]>("/api-keys"),
  createBatch: (items: Array<{ name: string; vendor: string; api_key: string }>) =>
    request<{ results: ApiCredentialBatchResult[] }>("/api-keys/batch", {
      method: "POST",
      body: JSON.stringify({ items }),
    }),
  rename: (id: number, name: string) =>
    request<ApiCredential>(`/api-keys/${id}`, {
      method: "PUT",
      body: JSON.stringify({ name }),
    }),
  sync: (id: number) =>
    request<{ credential: ApiCredential; sync: DeviceSyncStats }>(`/api-keys/${id}/sync`, {
      method: "POST",
    }),
  syncAll: () =>
    request<{ results: ApiCredentialBatchResult[] }>("/api-keys/sync-all", {
      method: "POST",
    }),
  delete: (id: number) =>
    request<void>(`/api-keys/${id}`, { method: "DELETE" }),
};

// ── Schedules ────────────────────────────────────────────

export const schedulesApi = {
  list: (deviceId: number) => request<Schedule[]>(`/devices/${deviceId}/schedules`),
  create: (deviceId: number, data: { name: string; cron: string; type: string; params?: Record<string, unknown> }) =>
    request<Schedule>(`/devices/${deviceId}/schedules`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  update: (id: number, data: Partial<Schedule>) =>
    request<Schedule>(`/devices/schedules/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  delete: (id: number) => request<void>(`/devices/schedules/${id}`, { method: "DELETE" }),
};

// ── Settings ─────────────────────────────────────────────

export const settingsApi = {
  get: () => request<Settings>("/settings"),
  update: (data: Partial<Settings>) =>
    request<Settings>("/settings", { method: "PUT", body: JSON.stringify(data) }),
};

// ── Schema ───────────────────────────────────────────────

export const schemaApi = {
  getScheduleTypes: () => request<ScheduleTypeSchema>("/schema/schedule-types"),
};

export const authApi = {
  status: async (token: string | null = getToken()): Promise<AuthStatus> => {
    const headers: Record<string, string> = {};
    if (token) headers.Authorization = `Bearer ${token}`;
    const response = await fetch(`${API_BASE}/auth/status`, { headers });
    if (!response.ok) throw new ApiError("Unable to check authentication status");
    return response.json();
  },
};
