import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  ScheduleFieldSchema,
  ScheduleTypeDefinition,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  scheduleFieldDescription,
  scheduleFieldLabel,
  scheduleOptionLabel,
} from "@/i18n/metadata";

interface ScheduleFormProps {
  type: string;
  definition: ScheduleTypeDefinition;
  values: Record<string, unknown>;
  errors: Record<string, string>;
  disabled?: boolean;
  onChange: (values: Record<string, unknown>) => void;
}

function fieldId(key: string) {
  return `schedule-param-${key}`;
}

export function ScheduleForm({
  type,
  definition,
  values,
  errors,
  disabled = false,
  onChange,
}: ScheduleFormProps) {
  const { t } = useTranslation();
  const [displayOpen, setDisplayOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const visibleFields = Object.entries(definition.fields).filter(
    ([, field]) => !field.hidden
  );
  const mainFields = visibleFields.filter(
    ([, field]) => field.section === "main"
  );
  const displayFields = visibleFields.filter(
    ([, field]) => field.section === "display"
  );
  const advancedFields = visibleFields.filter(
    ([, field]) => field.section === "advanced"
  );

  function updateField(key: string, value: unknown) {
    const next = { ...values };
    if (value === undefined || value === "") delete next[key];
    else next[key] = value;
    onChange(next);
  }

  function renderControl(key: string, field: ScheduleFieldSchema) {
    const value = values[key];
    const invalid = Boolean(errors[key]);
    const id = fieldId(key);

    if (field.options) {
      const selected = field.options.find(
        (option) => Object.is(option.value, value)
      );
      return (
        <Select
          value={selected ? JSON.stringify(selected.value) : ""}
          onValueChange={(encoded) => {
            const option = field.options?.find(
              (candidate) => JSON.stringify(candidate.value) === encoded
            );
            updateField(key, option?.value);
          }}
          disabled={disabled}
        >
          <SelectTrigger id={id} className="w-full" aria-invalid={invalid}>
            <SelectValue placeholder={t("schedules.selectField", { field: scheduleFieldLabel(t, type, key, field) })} />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {field.options.map((option) => (
                <SelectItem
                  key={JSON.stringify(option.value)}
                  value={JSON.stringify(option.value)}
                >
                  {scheduleOptionLabel(t, option.value, option.label)}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      );
    }

    if (field.type === "boolean") {
      return (
        <Switch
          id={id}
          checked={Boolean(value)}
          onCheckedChange={(checked) => updateField(key, checked)}
          aria-invalid={invalid}
          disabled={disabled}
        />
      );
    }

    if (field.input === "textarea") {
      return (
        <Textarea
          id={id}
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(event) => updateField(key, event.target.value)}
          aria-invalid={invalid}
          disabled={disabled}
          rows={4}
        />
      );
    }

    const inputType =
      field.type === "integer" || field.type === "number"
        ? "number"
        : field.input;
    return (
      <Input
        id={id}
        type={inputType}
        value={value === undefined || value === null ? "" : String(value)}
        onChange={(event) => {
          const raw = event.target.value;
          if (!raw) updateField(key, undefined);
          else if (field.type === "integer" || field.type === "number") {
            updateField(key, Number(raw));
          } else updateField(key, raw);
        }}
        aria-invalid={invalid}
        disabled={disabled}
        autoComplete={field.sensitive ? "new-password" : undefined}
      />
    );
  }

  function renderField(key: string, field: ScheduleFieldSchema) {
    const invalid = Boolean(errors[key]);
    if (field.type === "boolean") {
      return (
        <Field key={key} orientation="horizontal" data-invalid={invalid}>
          <div className="flex flex-1 flex-col gap-1">
            <FieldLabel htmlFor={fieldId(key)}>{scheduleFieldLabel(t, type, key, field)}</FieldLabel>
            {field.description && (
              <FieldDescription>{scheduleFieldDescription(t, type, key, field)}</FieldDescription>
            )}
            <FieldError>{errors[key]}</FieldError>
          </div>
          {renderControl(key, field)}
        </Field>
      );
    }
    return (
      <Field key={key} data-invalid={invalid}>
        <FieldLabel htmlFor={fieldId(key)}>
          {scheduleFieldLabel(t, type, key, field)}
          {field.required && <span aria-hidden="true">*</span>}
        </FieldLabel>
        {renderControl(key, field)}
        {field.description && (
          <FieldDescription>{scheduleFieldDescription(t, type, key, field)}</FieldDescription>
        )}
        <FieldError>{errors[key]}</FieldError>
      </Field>
    );
  }

  function renderSection(
    title: string,
    fields: Array<[string, ScheduleFieldSchema]>,
    open: boolean,
    setOpen: (open: boolean) => void
  ) {
    if (!fields.length) return null;
    return (
      <Collapsible open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <Button type="button" variant="ghost" className="w-full justify-between">
            {title}
            <ChevronDown data-icon="inline-end" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-4">
          <FieldGroup>{fields.map(([key, field]) => renderField(key, field))}</FieldGroup>
        </CollapsibleContent>
      </Collapsible>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <FieldGroup>{mainFields.map(([key, field]) => renderField(key, field))}</FieldGroup>
      {renderSection(t("schedules.displayOptions"), displayFields, displayOpen, setDisplayOpen)}
      {renderSection(t("schedules.advancedOptions"), advancedFields, advancedOpen, setAdvancedOpen)}
    </div>
  );
}
