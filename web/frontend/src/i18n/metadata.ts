import type { TFunction } from "i18next";

import type {
  DeviceModel,
  ScheduleFieldSchema,
  ScheduleTypeDefinition,
  Vendor,
} from "@/lib/api";

function translated(
  t: TFunction,
  key: string,
  fallback: string
): string {
  return t(key, { defaultValue: fallback });
}

export function vendorDescription(t: TFunction, vendor: Vendor): string {
  return translated(
    t,
    `metadata.vendors.${vendor.id}.description`,
    vendor.description
  );
}

export function vendorCredentialHint(t: TFunction, vendor: Vendor): string {
  return translated(
    t,
    `metadata.vendors.${vendor.id}.credentialHint`,
    vendor.credential_hint
  );
}

export function modelDescription(t: TFunction, model: DeviceModel): string {
  return translated(
    t,
    `metadata.models.${model.id}.description`,
    model.description
  );
}

export function modelDeviceIdLabel(t: TFunction, model: DeviceModel): string {
  return translated(
    t,
    `metadata.models.${model.id}.deviceIdLabel`,
    model.device_id_label
  );
}

export function scheduleTypeLabel(
  t: TFunction,
  type: string,
  fallback: string
): string {
  return translated(t, `metadata.schedule.${type}.label`, fallback);
}

export function scheduleTypeDescription(
  t: TFunction,
  type: string,
  definition: ScheduleTypeDefinition
): string {
  return translated(
    t,
    `metadata.schedule.${type}.description`,
    definition.description
  );
}

export function scheduleFieldLabel(
  t: TFunction,
  type: string,
  key: string,
  field: ScheduleFieldSchema
): string {
  const typeKey = `metadata.schedule.${type}.fields.${key}.label`;
  const typeValue = t(typeKey, { defaultValue: "" });
  if (typeValue) return typeValue;
  return translated(t, `metadata.fields.${key}.label`, field.label);
}

export function scheduleFieldDescription(
  t: TFunction,
  type: string,
  key: string,
  field: ScheduleFieldSchema
): string {
  if (!field.description) return "";
  const typeKey = `metadata.schedule.${type}.fields.${key}.description`;
  const typeValue = t(typeKey, { defaultValue: "" });
  if (typeValue) return typeValue;
  return translated(
    t,
    `metadata.fields.${key}.description`,
    field.description
  );
}

export function scheduleOptionLabel(
  t: TFunction,
  value: unknown,
  fallback: string
): string {
  return translated(t, `metadata.options.${String(value)}`, fallback);
}
