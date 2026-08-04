import type { DeviceStatusPolicy } from "@/lib/api";

export function formatStatusTimestamp(
  value: string | null,
  locale?: string
): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function statusRefreshCompleted(
  policy: DeviceStatusPolicy,
  requestedAt: string
): boolean {
  if (!policy.last_attempt_at) return false;
  return new Date(policy.last_attempt_at).getTime() >= new Date(requestedAt).getTime();
}

export function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}
