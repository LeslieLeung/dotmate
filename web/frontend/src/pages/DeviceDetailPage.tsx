import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarClock,
  Pencil,
  Play,
  Plus,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import {
  ApiError,
  devicesApi,
  schedulesApi,
  type Device,
  type Schedule,
  type ScheduleTypeSchema,
} from "@/lib/api";
import { ScheduleForm } from "@/components/ScheduleForm";
import { RemoteDevicePanel } from "@/components/RemoteDevicePanel";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
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
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import {
  getDefaultParams,
  normalizeParams,
  valuesEqual,
} from "@/lib/schedule-form";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  scheduleFieldLabel,
  scheduleTypeDescription,
  scheduleTypeLabel,
} from "@/i18n/metadata";

type DiscardAction = "close" | "type" | null;

interface FormDraft {
  name: string;
  cron: string;
  type: string;
  params: Record<string, unknown>;
}

const EMPTY_FORM_DRAFT: FormDraft = {
  name: "",
  cron: "",
  type: "",
  params: {},
};

function draftsEqual(left: FormDraft, right: FormDraft) {
  return (
    left.name === right.name &&
    left.cron === right.cron &&
    left.type === right.type &&
    valuesEqual(normalizeParams(left.params), normalizeParams(right.params))
  );
}

function isPortaledOverlayTarget(target: EventTarget | null) {
  if (!(target instanceof Element)) return false;
  return Boolean(
    target.closest('[data-slot="select-content"]') ||
      target.closest('[data-slot="alert-dialog-content"]') ||
      target.closest('[role="listbox"]') ||
      target.closest('[role="alertdialog"]')
  );
}

export function DeviceDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const deviceId = Number(id);

  const [device, setDevice] = useState<Device | null>(null);
  const [schema, setSchema] = useState<ScheduleTypeSchema>({});
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Schedule | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [runningScheduleId, setRunningScheduleId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [discardAction, setDiscardAction] = useState<DiscardAction>(null);
  const [pendingType, setPendingType] = useState<string | null>(null);
  const suppressSheetCloseRef = useRef(false);

  const [formName, setFormName] = useState("");
  const [formCron, setFormCron] = useState("");
  const [formType, setFormType] = useState("");
  const [formParams, setFormParams] = useState<Record<string, unknown>>({});
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [initialDraft, setInitialDraft] = useState<FormDraft>(EMPTY_FORM_DRAFT);

  const currentDraft: FormDraft = {
    name: formName,
    cron: formCron,
    type: formType,
    params: formParams,
  };
  const formChanged = !draftsEqual(initialDraft, currentDraft);

  const selectedDefinition = schema[formType];
  const unsupportedExistingType = Boolean(
    editingSchedule && !schema[editingSchedule.type]
  );

  const loadData = useCallback(async () => {
    setLoadFailed(false);
    try {
      const deviceData = await devicesApi.get(deviceId);
      const schemaData = await devicesApi.scheduleTypes(deviceId);
      setDevice(deviceData);
      setSchema(schemaData);
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }, [deviceId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  function resetErrors() {
    setFormErrors({});
  }

  function clearFieldErrors(keys: string[]) {
    setFormErrors((current) =>
      Object.fromEntries(
        Object.entries(current).filter(([key]) => !keys.includes(key))
      )
    );
  }

  function openCreateSheet() {
    setInitialDraft(EMPTY_FORM_DRAFT);
    setEditingSchedule(null);
    setFormName("");
    setFormCron("");
    setFormType("");
    setFormParams({});
    resetErrors();
    setSheetOpen(true);
  }

  function openEditSheet(schedule: Schedule) {
    const draft = {
      name: schedule.name,
      cron: schedule.cron || "",
      type: schedule.type,
      params: schedule.params || {},
    };
    setInitialDraft(draft);
    setEditingSchedule(schedule);
    setFormName(draft.name);
    setFormCron(draft.cron);
    setFormType(draft.type);
    setFormParams(draft.params);
    resetErrors();
    setSheetOpen(true);
  }

  function closeSheet() {
    setInitialDraft(currentDraft);
    setSheetOpen(false);
    setDiscardAction(null);
    setPendingType(null);
  }

  function suppressNextSheetClose() {
    suppressSheetCloseRef.current = true;
    window.setTimeout(() => {
      suppressSheetCloseRef.current = false;
    }, 0);
  }

  function requestSheetClose() {
    if (saving || discardAction || suppressSheetCloseRef.current) return;
    if (formChanged) setDiscardAction("close");
    else closeSheet();
  }

  function applyType(nextType: string) {
    setFormType(nextType);
    setFormParams(getDefaultParams(schema[nextType]));
    setFormErrors((current) => {
      const { type: _type, ...rest } = current;
      return rest;
    });
    setPendingType(null);
  }

  function requestTypeChange(nextType: string) {
    if (nextType === formType) return;
    const defaultParams = selectedDefinition
      ? getDefaultParams(selectedDefinition)
      : {};
    if (
      formType &&
      !valuesEqual(normalizeParams(formParams), normalizeParams(defaultParams))
    ) {
      suppressNextSheetClose();
      setPendingType(nextType);
      setDiscardAction("type");
      return;
    }
    applyType(nextType);
  }

  function dismissDiscardDialog() {
    suppressNextSheetClose();
    setDiscardAction(null);
    setPendingType(null);
  }

  function validateForm() {
    const errors: Record<string, string> = {};
    if (!formName.trim()) errors.name = t("schedules.nameRequired");
    if (!formCron.trim()) errors.cron = t("schedules.cronRequired");
    else if (formCron.trim().split(/\s+/).length !== 5) {
      errors.cron = t("schedules.cronParts");
    }
    if (!formType) errors.type = t("schedules.typeRequired");
    if (selectedDefinition) {
      for (const [key, field] of Object.entries(selectedDefinition.fields)) {
        const value = formParams[key];
        if (field.required && (value === undefined || value === null || value === "")) {
          errors[key] = t("schedules.fieldRequired", {
            field: scheduleFieldLabel(t, formType, key, field),
          });
        }
      }
    }
    setFormErrors(errors);
    if (Object.keys(errors).length) {
      window.setTimeout(() => {
        document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
      });
      return false;
    }
    return true;
  }

  async function handleSave() {
    if (!validateForm() || saving) return;
    setSaving(true);
    resetErrors();
    try {
      if (editingSchedule) {
        const update = unsupportedExistingType
          ? { name: formName.trim(), cron: formCron.trim() }
          : {
              name: formName.trim(),
              cron: formCron.trim(),
              type: formType,
              params: formParams,
            };
        await schedulesApi.update(editingSchedule.id, update);
        toast.success(t("schedules.updated"));
      } else {
        await schedulesApi.create(deviceId, {
          name: formName.trim(),
          cron: formCron.trim(),
          type: formType,
          params: formParams,
        });
        toast.success(t("schedules.created"));
      }
      closeSheet();
      await loadData();
    } catch (error) {
      if (error instanceof ApiError) {
        const fieldErrors = { ...error.fieldErrors };
        if (error.message && !fieldErrors.cron) {
          fieldErrors.cron = error.message;
        }
        setFormErrors(fieldErrors);
        toast.error(error.message);
        window.setTimeout(() => {
          document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
        });
      } else {
        toast.error(t("schedules.saveFailed"));
      }
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteConfirm || deleting) return;
    setDeleting(true);
    try {
      await schedulesApi.delete(deleteConfirm.id);
      toast.success(t("schedules.deleted"));
      setDeleteConfirm(null);
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("schedules.deleteFailed"));
    } finally {
      setDeleting(false);
    }
  }

  async function handleRun(schedule: Schedule) {
    if (runningScheduleId !== null) return;
    setRunningScheduleId(schedule.id);
    try {
      await schedulesApi.run(schedule.id);
      toast.success(t("schedules.pushed"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("schedules.pushFailed"));
    } finally {
      setRunningScheduleId(null);
    }
  }

  const schedules = device?.schedules ?? [];
  const scheduleCount = schedules.length;

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-14 w-64" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (loadFailed || !device) {
    return (
      <Empty className="min-h-80 border">
        <EmptyHeader>
          <EmptyMedia variant="icon"><CalendarClock /></EmptyMedia>
          <EmptyTitle>{t("schedules.unableToLoadDevice")}</EmptyTitle>
          <EmptyDescription>{t("auth.connectionHint")}</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button onClick={() => void loadData()}>{t("common.tryAgain")}</Button>
          <Button variant="ghost" onClick={() => navigate("/devices")}>{t("schedules.backToDevices")}</Button>
        </EmptyContent>
      </Empty>
    );
  }

  function renderActions(schedule: Schedule) {
    const isRunning = runningScheduleId === schedule.id;
    return (
      <div className="flex justify-end gap-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("schedules.runAria", { name: schedule.name })}
              onClick={() => void handleRun(schedule)}
              disabled={runningScheduleId !== null}
            >
              {isRunning ? <Spinner /> : <Play />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("schedules.runNow")}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("schedules.editAria", { name: schedule.name })}
              onClick={() => openEditSheet(schedule)}
              disabled={runningScheduleId !== null}
            >
              <Pencil />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("schedules.editAction")}</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("schedules.deleteAria", { name: schedule.name })}
              onClick={() => setDeleteConfirm(schedule)}
              disabled={runningScheduleId !== null}
            >
              <Trash2 />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{t("schedules.deleteAction")}</TooltipContent>
        </Tooltip>
      </div>
    );
  }

  function renderSummary(schedule: Schedule) {
    if (!schedule.summary.length) return <span className="text-muted-foreground">—</span>;
    return (
      <dl className="flex flex-col gap-1">
        {schedule.summary.map((item) => (
          <div key={item.label} className="flex min-w-0 gap-1 text-sm">
            <dt className="text-muted-foreground">
              {item.field
                ? t(`metadata.fields.${item.field}.label`, { defaultValue: item.label })
                : item.label}:
            </dt>
            <dd className="truncate">
              {item.field === "page_id" && item.raw_value !== undefined
                ? t("metadata.page", { value: item.raw_value })
                : item.value}
            </dd>
          </div>
        ))}
      </dl>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          aria-label={t("schedules.backAria")}
          onClick={() => navigate("/devices")}
        >
          <ArrowLeft />
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold">{device.name}</h1>
          <p className="truncate font-mono text-sm text-muted-foreground">
            {device.device_id}
          </p>
          <p className="text-sm text-muted-foreground">
            {device.vendor_label || device.vendor} · {device.device_model_label} ·{" "}
            {device.display_width}×{device.display_height} · {device.api_credential_name}
          </p>
        </div>
      </div>

      {device.vendor_capabilities.some((capability) =>
        ["status", "settings", "content", "next"].includes(capability)
      ) && <RemoteDevicePanel device={device} />}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-medium">{t("schedules.title")}</h2>
          <p className="text-sm text-muted-foreground">
            {t("schedules.count", { count: scheduleCount })}
          </p>
        </div>
        <Button onClick={openCreateSheet}>
          <Plus data-icon="inline-start" />
          {t("schedules.add")}
        </Button>
      </div>

      {schedules.length === 0 ? (
        <Card>
          <CardContent>
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><CalendarClock /></EmptyMedia>
                <EmptyTitle>{t("schedules.emptyTitle")}</EmptyTitle>
                <EmptyDescription>{t("schedules.emptyDescription")}</EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button onClick={openCreateSheet}>
                  <Plus data-icon="inline-start" />
                  {t("schedules.add")}
                </Button>
              </EmptyContent>
            </Empty>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="hidden md:block">
            <CardHeader>
              <CardTitle>{t("schedules.configured")}</CardTitle>
              <CardDescription>{t("schedules.configuredDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("common.name")}</TableHead>
                    <TableHead>{t("common.type")}</TableHead>
                    <TableHead>{t("schedules.schedule")}</TableHead>
                    <TableHead>{t("common.summary")}</TableHead>
                    <TableHead className="w-32 text-right">{t("common.actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {schedules.map((schedule) => (
                    <TableRow key={schedule.id}>
                      <TableCell className="font-medium">{schedule.name}</TableCell>
                      <TableCell>
                        <div className="flex min-w-0 flex-col gap-0.5">
                          <span className="truncate text-sm font-medium">{scheduleTypeLabel(t, schedule.type, schedule.type_label)}</span>
                          <code className="truncate text-xs text-muted-foreground">{schedule.type}</code>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{schedule.cron || "—"}</TableCell>
                      <TableCell className="max-w-xs">{renderSummary(schedule)}</TableCell>
                      <TableCell>{renderActions(schedule)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <div className="flex flex-col gap-3 md:hidden">
            {schedules.map((schedule) => (
              <Card key={schedule.id}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <CardTitle className="truncate">{schedule.name}</CardTitle>
                      <CardDescription>{scheduleTypeLabel(t, schedule.type, schedule.type_label)}</CardDescription>
                    </div>
                    {renderActions(schedule)}
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div>
                    <p className="text-xs text-muted-foreground">{t("schedules.schedule")}</p>
                    <code className="text-sm">{schedule.cron || "—"}</code>
                  </div>
                  {renderSummary(schedule)}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}

      <Sheet
        open={sheetOpen}
        onOpenChange={(open) => {
          if (!open) requestSheetClose();
        }}
      >
        <SheetContent
          className="w-full gap-0 sm:max-w-xl"
          showCloseButton={!saving}
          onPointerDownOutside={(event) => {
            if (isPortaledOverlayTarget(event.target)) event.preventDefault();
          }}
          onInteractOutside={(event) => {
            if (isPortaledOverlayTarget(event.target) || discardAction) {
              event.preventDefault();
            }
          }}
          onFocusOutside={(event) => {
            if (isPortaledOverlayTarget(event.target) || discardAction) {
              event.preventDefault();
            }
          }}
        >
          <SheetHeader>
            <SheetTitle>{editingSchedule ? t("schedules.edit") : t("schedules.add")}</SheetTitle>
            <SheetDescription>
              {editingSchedule
                ? t("schedules.editDescription")
                : t("schedules.addDescription")}
            </SheetDescription>
          </SheetHeader>
          <Separator />

          <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-4">
            <FieldGroup>
              <Field data-invalid={Boolean(formErrors.name)}>
                <FieldLabel htmlFor="schedule-name">{t("common.name")}*</FieldLabel>
                <Input
                  id="schedule-name"
                  value={formName}
                  onChange={(event) => {
                    setFormName(event.target.value);
                    clearFieldErrors(["name"]);
                  }}
                  placeholder={t("schedules.namePlaceholder")}
                  aria-invalid={Boolean(formErrors.name)}
                  disabled={saving}
                  autoFocus
                />
                <FieldDescription>{t("schedules.nameHint")}</FieldDescription>
                <FieldError>{formErrors.name}</FieldError>
              </Field>

              <Field data-invalid={Boolean(formErrors.cron)}>
                <FieldLabel htmlFor="schedule-cron">{t("schedules.cron")}*</FieldLabel>
                <Input
                  id="schedule-cron"
                  className="font-mono"
                  value={formCron}
                  onChange={(event) => {
                    setFormCron(event.target.value);
                    clearFieldErrors(["cron"]);
                  }}
                  placeholder="*/5 * * * *"
                  aria-invalid={Boolean(formErrors.cron)}
                  disabled={saving}
                />
                <FieldDescription>
                  {t("schedules.cronHint")}
                </FieldDescription>
                <FieldError>{formErrors.cron}</FieldError>
              </Field>

              <Field data-invalid={Boolean(formErrors.type)} data-disabled={unsupportedExistingType}>
                <FieldLabel htmlFor="schedule-type">{t("schedules.type")}*</FieldLabel>
                <Select
                  value={formType}
                  onValueChange={requestTypeChange}
                  disabled={saving || unsupportedExistingType}
                >
                  <SelectTrigger id="schedule-type" className="w-full" aria-invalid={Boolean(formErrors.type)}>
                    <SelectValue placeholder={t("schedules.selectType")} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {unsupportedExistingType && editingSchedule && (
                        <SelectItem value={editingSchedule.type}>{scheduleTypeLabel(t, editingSchedule.type, editingSchedule.type_label)}</SelectItem>
                      )}
                      {Object.entries(schema).map(([type, definition]) => (
                        <SelectItem key={type} value={type}>{scheduleTypeLabel(t, type, definition.label)}</SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                {selectedDefinition && (
                  <FieldDescription>{scheduleTypeDescription(t, formType, selectedDefinition)}</FieldDescription>
                )}
                {unsupportedExistingType && (
                  <FieldDescription>
                    {t("schedules.legacyHint")}
                  </FieldDescription>
                )}
                <FieldError>{formErrors.type}</FieldError>
              </Field>
            </FieldGroup>

            {selectedDefinition && (
              <>
                <Separator />
                <ScheduleForm
                  key={formType}
                  type={formType}
                  definition={selectedDefinition}
                  values={formParams}
                  errors={formErrors}
                  disabled={saving}
                  onChange={(values) => {
                    const changedKeys = Object.keys(selectedDefinition.fields).filter(
                      (key) => !Object.is(formParams[key], values[key])
                    );
                    setFormParams(values);
                    clearFieldErrors(changedKeys);
                  }}
                />
              </>
            )}
          </div>

          <Separator />
          <SheetFooter className="flex-row justify-end">
            <Button type="button" variant="outline" onClick={requestSheetClose} disabled={saving}>{t("common.cancel")}</Button>
            <Button type="button" onClick={() => void handleSave()} disabled={saving}>
              {saving && <Spinner data-icon="inline-start" />}
              {saving ? t("common.saving") : editingSchedule ? t("devices.saveChanges") : t("schedules.createSchedule")}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <AlertDialog open={Boolean(deleteConfirm)} onOpenChange={(open) => !open && !deleting && setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("schedules.deleteTitle", { name: deleteConfirm?.name })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("schedules.deleteDescription", {
                type: deleteConfirm
                  ? scheduleTypeLabel(t, deleteConfirm.type, deleteConfirm.type_label)
                  : t("schedules.schedule"),
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={(event) => {
              event.preventDefault();
              void handleDelete();
            }} disabled={deleting}>
              {deleting && <Spinner data-icon="inline-start" />}
              {deleting ? t("common.deleting") : t("common.delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={Boolean(discardAction)}
        onOpenChange={(open) => {
          if (!open) dismissDiscardDialog();
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {discardAction === "type"
                ? t("schedules.changeTypeTitle")
                : t("schedules.discardTitle")}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {discardAction === "type"
                ? t("schedules.changeTypeDescription")
                : t("schedules.discardDescription")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={dismissDiscardDialog}>
              {discardAction === "type" ? t("schedules.keepType") : t("schedules.keepEditing")}
            </AlertDialogCancel>
            <AlertDialogAction
              variant={discardAction === "type" ? "default" : "destructive"}
              onClick={(event) => {
                event.preventDefault();
                const action = discardAction;
                const nextType = pendingType;
                dismissDiscardDialog();
                if (action === "type" && nextType) applyType(nextType);
                else if (action === "close") closeSheet();
              }}
            >
              {discardAction === "type" ? t("schedules.changeType") : t("schedules.discardChanges")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
