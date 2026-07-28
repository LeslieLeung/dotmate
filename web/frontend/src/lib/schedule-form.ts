import type { ScheduleTypeDefinition } from "@/lib/api";

export function getDefaultParams(
  definition: ScheduleTypeDefinition
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(definition.fields)
      .filter(([, field]) => field.default !== undefined && field.default !== null)
      .map(([key, field]) => [key, field.default])
  );
}

export function normalizeParams(
  params: Record<string, unknown>
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null && value !== ""
    )
  );
}

export function valuesEqual(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (Array.isArray(left) && Array.isArray(right)) {
    return (
      left.length === right.length &&
      left.every((value, index) => valuesEqual(value, right[index]))
    );
  }
  if (
    left !== null &&
    right !== null &&
    typeof left === "object" &&
    typeof right === "object"
  ) {
    const leftEntries = Object.entries(left);
    const rightRecord = right as Record<string, unknown>;
    return (
      leftEntries.length === Object.keys(rightRecord).length &&
      leftEntries.every(
        ([key, value]) =>
          Object.prototype.hasOwnProperty.call(rightRecord, key) &&
          valuesEqual(value, rightRecord[key])
      )
    );
  }
  return false;
}
