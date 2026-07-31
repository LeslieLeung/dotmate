import { useCallback, useEffect, useState } from "react";
import { BatteryCharging, Clock3, RefreshCw, Settings2, SkipForward, Wifi } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Field,
  FieldContent,
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
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  devicesApi,
  type Device,
  type DeviceStatusPolicy,
  type RemoteContent,
  type RemoteDeviceSettings,
  type RemoteDeviceStatus,
  type RemoteTimezone,
} from "@/lib/api";
import {
  formatStatusTimestamp,
  statusRefreshCompleted,
  wait,
} from "@/lib/device-status";

export function RemoteDevicePanel({ device }: { device: Device }) {
  const { t, i18n } = useTranslation();
  const supportsStatus = device.vendor_capabilities.includes("status");
  const supportsSettings = device.vendor_capabilities.includes("settings");
  const supportsTimezones = device.vendor_capabilities.includes("timezones");
  const supportsContent = device.vendor_capabilities.includes("content");
  const supportsNext = device.vendor_capabilities.includes("next");
  const [settings, setSettings] = useState<RemoteDeviceSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsError, setSettingsError] = useState(false);
  const [content, setContent] = useState<RemoteContent[]>([]);
  const [contentLoading, setContentLoading] = useState(true);
  const [contentError, setContentError] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [timezones, setTimezones] = useState<RemoteTimezone[]>([]);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [alias, setAlias] = useState("");
  const [location, setLocation] = useState("");
  const [timezone, setTimezone] = useState("");
  const [powerMinutes, setPowerMinutes] = useState("");
  const [batteryMinutes, setBatteryMinutes] = useState("");
  const [sleepEnabled, setSleepEnabled] = useState(false);
  const [sleepStart, setSleepStart] = useState("22:00");
  const [sleepEnd, setSleepEnd] = useState("07:00");
  const [remoteStatus, setRemoteStatus] = useState<RemoteDeviceStatus | null>(device.remote_status);
  const [statusPolicy, setStatusPolicy] = useState<DeviceStatusPolicy>(device.status_policy);
  const [statusRefreshing, setStatusRefreshing] = useState(false);
  const [policyOpen, setPolicyOpen] = useState(false);
  const [policySaving, setPolicySaving] = useState(false);
  const [policyMode, setPolicyMode] = useState<"follow" | "custom">(
    device.status_policy.refresh_interval_minutes === null ? "follow" : "custom"
  );
  const [policyMinutes, setPolicyMinutes] = useState(
    device.status_policy.refresh_interval_minutes?.toString() ?? ""
  );
  const [policyError, setPolicyError] = useState("");

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError(false);
    try {
      setSettings(await devicesApi.remoteSettings(device.id));
    } catch {
      setSettingsError(true);
    } finally {
      setSettingsLoading(false);
    }
  }, [device.id]);

  const loadContent = useCallback(async () => {
    setContentLoading(true);
    setContentError(false);
    try {
      setContent(await devicesApi.remoteContent(device.id));
    } catch {
      setContentError(true);
    } finally {
      setContentLoading(false);
    }
  }, [device.id]);

  useEffect(() => {
    if (supportsSettings) void loadSettings();
    if (supportsContent) void loadContent();
  }, [loadContent, loadSettings, supportsContent, supportsSettings]);

  useEffect(() => {
    setRemoteStatus(device.remote_status);
    setStatusPolicy(device.status_policy);
  }, [device.remote_status, device.status_policy]);

  async function openSettings() {
    if (!settings) return;
    setAlias(settings.alias ?? "");
    setLocation(settings.location ?? "");
    setTimezone(settings.timezone ?? "");
    setPowerMinutes(settings.power_interval_minutes?.toString() ?? "");
    setBatteryMinutes(settings.battery_interval_minutes?.toString() ?? "");
    setSleepEnabled(settings.sleep?.enabled ?? false);
    setSleepStart(settings.sleep?.start ?? "22:00");
    setSleepEnd(settings.sleep?.end ?? "07:00");
    setFormErrors({});
    setSheetOpen(true);
    if (supportsTimezones && !timezones.length) {
      try {
        setTimezones(await devicesApi.remoteTimezones(device.id));
      } catch (error) {
        toast.error(error instanceof Error ? error.message : t("remote.timezonesFailed"));
      }
    }
  }

  function validateForm() {
    const errors: Record<string, string> = {};
    const power = powerMinutes ? Number(powerMinutes) : null;
    const battery = batteryMinutes ? Number(batteryMinutes) : null;
    if (power !== null && (!Number.isInteger(power) || power < 1 || power > 720)) errors.power_interval_minutes = t("remote.wholeNumber");
    if (battery !== null && (!Number.isInteger(battery) || battery < 1 || battery > 720)) errors.battery_interval_minutes = t("remote.wholeNumber");
    if (!/^\d{2}:\d{2}$/.test(sleepStart)) errors.sleep_start = t("remote.timeFormat");
    if (!/^\d{2}:\d{2}$/.test(sleepEnd)) errors.sleep_end = t("remote.timeFormat");
    if (sleepStart === sleepEnd) errors.sleep_end = t("remote.timeDifferent");
    if (supportsTimezones && !timezone) errors.timezone = t("remote.timezoneRequired");
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function saveSettings() {
    if (!validateForm()) return;
    setSaving(true);
    try {
      const payload: Partial<RemoteDeviceSettings> = {
        alias: alias.trim(),
        location: location.trim(),
        power_interval_minutes: powerMinutes ? Number(powerMinutes) : null,
        battery_interval_minutes: batteryMinutes ? Number(batteryMinutes) : null,
        sleep: { enabled: sleepEnabled, start: sleepStart, end: sleepEnd },
      };
      if (supportsTimezones) payload.timezone = timezone;
      const updated = await devicesApi.updateRemoteSettings(device.id, payload);
      setSettings(updated);
      setSheetOpen(false);
      toast.success(t("remote.settingsUpdated"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("remote.settingsUpdateFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function switchNext() {
    setSwitching(true);
    try {
      await devicesApi.nextContent(device.id);
      toast.success(t("remote.contentSwitched"));
      await loadContent();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("remote.contentSwitchFailed"));
    } finally {
      setSwitching(false);
    }
  }

  async function refreshStatus() {
    if (statusRefreshing) return;
    setStatusRefreshing(true);
    try {
      const request = await devicesApi.refreshStatus(device.id);
      const deadline = Date.now() + 60_000;
      while (Date.now() < deadline) {
        await wait(2_000);
        const latest = await devicesApi.get(device.id);
        setRemoteStatus(latest.remote_status);
        setStatusPolicy(latest.status_policy);
        if (statusRefreshCompleted(latest.status_policy, request.requested_at)) {
          if (latest.status_policy.last_error) {
            toast.error(statusErrorText(latest.status_policy));
          } else {
            toast.success(t("remote.statusRefreshed"));
          }
          return;
        }
      }
      toast.info(t("devices.refreshContinues"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("remote.statusRefreshFailed"));
    } finally {
      setStatusRefreshing(false);
    }
  }

  function openPolicy() {
    const custom = statusPolicy.refresh_interval_minutes;
    setPolicyMode(custom === null ? "follow" : "custom");
    setPolicyMinutes(custom?.toString() ?? "");
    setPolicyError("");
    setPolicyOpen(true);
  }

  async function saveStatusPolicy() {
    let interval: number | null = null;
    if (policyMode === "custom") {
      interval = Number(policyMinutes);
      if (!Number.isInteger(interval) || interval < 1 || interval > 720) {
        setPolicyError(t("remote.wholeNumber"));
        return;
      }
    }
    setPolicySaving(true);
    try {
      const updated = await devicesApi.updateStatusPolicy(device.id, interval);
      setStatusPolicy(updated);
      setPolicyOpen(false);
      toast.success(interval === null ? t("remote.followSaved") : t("remote.intervalSaved"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("remote.intervalSaveFailed"));
    } finally {
      setPolicySaving(false);
    }
  }

  function contentSummary(item: RemoteContent) {
    return item.title || item.message || item.signature || item.link || (item.has_image ? t("remote.imageContent") : item.has_icon ? t("remote.iconContent") : "—");
  }

  function statusErrorText(policy: DeviceStatusPolicy): string {
    if (policy.last_error_code) {
      return t(`errors.${policy.last_error_code}`, {
        ...policy.last_error_params,
        defaultValue: t("errors.generic"),
      });
    }
    return policy.last_error || t("errors.generic");
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      {supportsStatus && <Card className="lg:col-span-2">
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle>{t("remote.statusTitle")}</CardTitle>
              <CardDescription>{t("remote.statusDescription")}</CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={openPolicy} disabled={policySaving}>
                <Clock3 data-icon="inline-start" />
                {t("remote.refreshInterval")}
              </Button>
              <Button onClick={() => void refreshStatus()} disabled={statusRefreshing}>
                {statusRefreshing
                  ? <Spinner data-icon="inline-start" />
                  : <RefreshCw data-icon="inline-start" />}
                {statusRefreshing ? t("devices.refreshing") : t("remote.refreshNow")}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {remoteStatus ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={statusPolicy.state === "stale" ? "outline" : "secondary"}>
                  {t(`status.${statusPolicy.state}`)}
                </Badge>
                <span className="font-medium">{remoteStatus.current || t("remote.unknownStatus")}</span>
                {remoteStatus.description && (
                  <span className="text-sm text-muted-foreground">{remoteStatus.description}</span>
                )}
              </div>
              <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><dt className="flex items-center gap-1 text-sm text-muted-foreground"><BatteryCharging />{t("devices.battery")}</dt><dd>{remoteStatus.battery || "—"}</dd></div>
                <div><dt className="flex items-center gap-1 text-sm text-muted-foreground"><Wifi />Wi-Fi</dt><dd>{remoteStatus.wifi || "—"}</dd></div>
                <div><dt className="text-sm text-muted-foreground">{t("remote.firmware")}</dt><dd>{remoteStatus.version || "—"}</dd></div>
                <div><dt className="text-sm text-muted-foreground">{t("remote.lastRender")}</dt><dd>{remoteStatus.last_render || "—"}</dd></div>
                <div><dt className="text-sm text-muted-foreground">{t("common.alias")}</dt><dd>{remoteStatus.alias || "—"}</dd></div>
                <div><dt className="text-sm text-muted-foreground">{t("common.location")}</dt><dd>{remoteStatus.location || "—"}</dd></div>
                <div><dt className="text-sm text-muted-foreground">{t("remote.display")}</dt><dd>{remoteStatus.rotated ? t("remote.rotated") : t("remote.normal")} · {remoteStatus.border === 1 ? t("remote.blackBorder") : t("remote.whiteBorder")}</dd></div>
                <div><dt className="text-sm text-muted-foreground">{t("remote.images")}</dt><dd>{remoteStatus.image_count}</dd></div>
                <div><dt className="text-sm text-muted-foreground">{t("remote.nextBattery")}</dt><dd>{remoteStatus.next_battery_render || "—"}</dd></div>
                <div><dt className="text-sm text-muted-foreground">{t("remote.nextPower")}</dt><dd>{remoteStatus.next_power_render || "—"}</dd></div>
              </dl>
            </>
          ) : statusPolicy.state === "error" ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><RefreshCw /></EmptyMedia>
                <EmptyTitle>{t("remote.unableStatus")}</EmptyTitle>
                <EmptyDescription>{statusPolicy.last_error ? statusErrorText(statusPolicy) : t("remote.tryRefresh")}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="flex flex-col gap-3">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-16 w-full" />
            </div>
          )}
          <Separator />
          <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <div><span className="text-muted-foreground">{t("remote.polling")}</span><p>{statusPolicy.refresh_interval_minutes === null ? t("remote.followDeviceDetail", { interval: statusPolicy.effective_interval_minutes ? t("remote.minutesSuffix", { count: statusPolicy.effective_interval_minutes }) : "", source: statusPolicy.interval_source && statusPolicy.interval_source !== "fallback" ? t("remote.sourceSuffix", { source: t(`remote.source.${statusPolicy.interval_source}`) }) : "" }) : t("remote.everyMinutes", { count: statusPolicy.refresh_interval_minutes })}</p></div>
            <div><span className="text-muted-foreground">{t("remote.lastSuccessful")}</span><p>{formatStatusTimestamp(statusPolicy.last_success_at, i18n.resolvedLanguage)}</p></div>
            <div><span className="text-muted-foreground">{t("remote.lastAttempted")}</span><p>{formatStatusTimestamp(statusPolicy.last_attempt_at, i18n.resolvedLanguage)}</p></div>
            <div><span className="text-muted-foreground">{t("remote.nextRefresh")}</span><p>{formatStatusTimestamp(statusPolicy.next_refresh_at, i18n.resolvedLanguage)}</p></div>
          </div>
          {statusPolicy.last_error && remoteStatus && (
            <p className="text-sm text-muted-foreground">{t("remote.lastRefreshFailed", { error: statusErrorText(statusPolicy) })}</p>
          )}
        </CardContent>
      </Card>}

      {supportsSettings && <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div><CardTitle>{t("remote.settingsTitle")}</CardTitle><CardDescription>{t("remote.settingsDescription", { vendor: device.vendor })}</CardDescription></div>
            <Button variant="outline" onClick={() => void openSettings()} disabled={!settings || settingsLoading}><Settings2 data-icon="inline-start" />{t("common.edit")}</Button>
          </div>
        </CardHeader>
        <CardContent>
          {settingsLoading ? <div className="flex flex-col gap-3"><Skeleton className="h-6 w-full" /><Skeleton className="h-6 w-full" /><Skeleton className="h-6 w-full" /></div> : settingsError ? <Empty><EmptyHeader><EmptyMedia variant="icon"><Settings2 /></EmptyMedia><EmptyTitle>{t("remote.unableSettings")}</EmptyTitle><EmptyDescription>{t("remote.settingsUnavailable")}</EmptyDescription></EmptyHeader><Button variant="outline" onClick={() => void loadSettings()}>{t("common.tryAgain")}</Button></Empty> : settings && <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm"><dt className="text-muted-foreground">{t("common.alias")}</dt><dd>{settings.alias || "—"}</dd><dt className="text-muted-foreground">{t("common.location")}</dt><dd>{settings.location || "—"}</dd><dt className="text-muted-foreground">{t("remote.timezone")}</dt><dd>{settings.timezone || "—"}</dd><dt className="text-muted-foreground">{t("remote.onPower")}</dt><dd>{settings.power_interval_minutes ? t("remote.minutes", { count: settings.power_interval_minutes }) : "—"}</dd><dt className="text-muted-foreground">{t("remote.onBattery")}</dt><dd>{settings.battery_interval_minutes ? t("remote.minutes", { count: settings.battery_interval_minutes }) : "—"}</dd><dt className="text-muted-foreground">{t("remote.sleep")}</dt><dd>{settings.sleep?.enabled ? `${settings.sleep.start}–${settings.sleep.end}` : t("common.disabled")}</dd></dl>}
        </CardContent>
      </Card>}

      {supportsContent && <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div><CardTitle>{t("remote.contentTitle")}</CardTitle><CardDescription>{t("remote.contentDescription")}</CardDescription></div>
            <div className="flex gap-1"><Button variant="outline" size="icon-sm" aria-label={t("remote.refreshContentAria")} onClick={() => void loadContent()} disabled={contentLoading}><RefreshCw /></Button>{supportsNext && <Button onClick={() => void switchNext()} disabled={switching}>{switching ? <Spinner data-icon="inline-start" /> : <SkipForward data-icon="inline-start" />}{t("remote.nextContent")}</Button>}</div>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {contentLoading ? <div className="flex flex-col gap-3 p-6"><Skeleton className="h-8 w-full" /><Skeleton className="h-8 w-full" /></div> : contentError ? <div className="p-6"><Empty><EmptyHeader><EmptyMedia variant="icon"><RefreshCw /></EmptyMedia><EmptyTitle>{t("remote.unableContent")}</EmptyTitle><EmptyDescription>{t("remote.contentUnavailable")}</EmptyDescription></EmptyHeader><Button variant="outline" onClick={() => void loadContent()}>{t("common.tryAgain")}</Button></Empty></div> : content.length ? <Table><TableHeader><TableRow><TableHead>{t("common.type")}</TableHead><TableHead>{t("common.key")}</TableHead><TableHead>{t("common.summary")}</TableHead></TableRow></TableHeader><TableBody>{content.map((item, index) => <TableRow key={`${item.key ?? item.type}-${index}`}><TableCell><Badge variant="secondary">{item.type}</Badge></TableCell><TableCell className="font-mono text-xs">{item.key || "—"}</TableCell><TableCell className="max-w-56 truncate">{contentSummary(item)}</TableCell></TableRow>)}</TableBody></Table> : <div className="p-6"><Empty><EmptyHeader><EmptyMedia variant="icon"><SkipForward /></EmptyMedia><EmptyTitle>{t("remote.noContent")}</EmptyTitle><EmptyDescription>{t("remote.noContentDescription")}</EmptyDescription></EmptyHeader></Empty></div>}
        </CardContent>
      </Card>}

      <Dialog open={policyOpen} onOpenChange={(open) => !policySaving && setPolicyOpen(open)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("remote.intervalTitle")}</DialogTitle>
            <DialogDescription>{t("remote.intervalDescription")}</DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="status-policy-mode">{t("remote.mode")}</FieldLabel>
              <Select value={policyMode} onValueChange={(value) => { setPolicyMode(value as "follow" | "custom"); setPolicyError(""); }} disabled={policySaving}>
                <SelectTrigger id="status-policy-mode" className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent><SelectGroup><SelectItem value="follow">{t("remote.followDevice")}</SelectItem><SelectItem value="custom">{t("remote.customInterval")}</SelectItem></SelectGroup></SelectContent>
              </Select>
              <FieldDescription>{t("remote.followHint")}</FieldDescription>
            </Field>
            {policyMode === "custom" && (
              <Field data-invalid={Boolean(policyError)}>
                <FieldLabel htmlFor="status-refresh-minutes">{t("remote.intervalMinutes")}</FieldLabel>
                <Input id="status-refresh-minutes" type="number" min="1" max="720" step="1" value={policyMinutes} onChange={(event) => { setPolicyMinutes(event.target.value); setPolicyError(""); }} aria-invalid={Boolean(policyError)} disabled={policySaving} />
                <FieldError>{policyError}</FieldError>
              </Field>
            )}
          </FieldGroup>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPolicyOpen(false)} disabled={policySaving}>{t("common.cancel")}</Button>
            <Button onClick={() => void saveStatusPolicy()} disabled={policySaving}>
              {policySaving && <Spinner data-icon="inline-start" />}
              {policySaving ? t("common.saving") : t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Sheet open={sheetOpen} onOpenChange={(open) => !saving && setSheetOpen(open)}>
        <SheetContent className="w-full gap-0 sm:max-w-xl" showCloseButton={!saving}>
          <SheetHeader><SheetTitle>{t("remote.editSettings")}</SheetTitle><SheetDescription>{t("remote.editSettingsDescription", { vendor: device.vendor })}</SheetDescription></SheetHeader><Separator />
          <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-4"><FieldGroup>
            <Field><FieldLabel htmlFor="remote-alias">{t("common.alias")}</FieldLabel><Input id="remote-alias" value={alias} onChange={(event) => setAlias(event.target.value)} maxLength={100} disabled={saving} /><FieldDescription>{t("remote.clearAliasHint")}</FieldDescription></Field>
            <Field><FieldLabel htmlFor="remote-location">{t("common.location")}</FieldLabel><Input id="remote-location" value={location} onChange={(event) => setLocation(event.target.value)} maxLength={100} disabled={saving} /></Field>
            {supportsTimezones && <Field data-invalid={Boolean(formErrors.timezone)}><FieldLabel>{t("remote.timezone")}*</FieldLabel><Select value={timezone} onValueChange={setTimezone} disabled={saving}><SelectTrigger className="w-full" aria-invalid={Boolean(formErrors.timezone)}><SelectValue placeholder={t("remote.selectTimezone")} /></SelectTrigger><SelectContent><SelectGroup>{timezones.map((item) => <SelectItem key={item.key} value={item.key}>{item.name} ({item.utc_offset_label})</SelectItem>)}</SelectGroup></SelectContent></Select><FieldError>{formErrors.timezone}</FieldError></Field>}
            <Field data-invalid={Boolean(formErrors.power_interval_minutes)}><FieldLabel htmlFor="power-interval">{t("remote.refreshPower")}</FieldLabel><Input id="power-interval" type="number" min="1" max="720" step="1" value={powerMinutes} onChange={(event) => setPowerMinutes(event.target.value)} aria-invalid={Boolean(formErrors.power_interval_minutes)} disabled={saving} /><FieldError>{formErrors.power_interval_minutes}</FieldError></Field>
            <Field data-invalid={Boolean(formErrors.battery_interval_minutes)}><FieldLabel htmlFor="battery-interval">{t("remote.refreshBattery")}</FieldLabel><Input id="battery-interval" type="number" min="1" max="720" step="1" value={batteryMinutes} onChange={(event) => setBatteryMinutes(event.target.value)} aria-invalid={Boolean(formErrors.battery_interval_minutes)} disabled={saving} /><FieldError>{formErrors.battery_interval_minutes}</FieldError></Field>
            <Field orientation="horizontal"><FieldContent><FieldLabel htmlFor="sleep-enabled">{t("remote.sleepSchedule")}</FieldLabel><FieldDescription>{t("remote.sleepDescription")}</FieldDescription></FieldContent><Switch id="sleep-enabled" checked={sleepEnabled} onCheckedChange={setSleepEnabled} disabled={saving} /></Field>
            <div className="grid grid-cols-2 gap-4"><Field data-invalid={Boolean(formErrors.sleep_start)}><FieldLabel htmlFor="sleep-start">{t("remote.starts")}</FieldLabel><Input id="sleep-start" type="time" value={sleepStart} onChange={(event) => setSleepStart(event.target.value)} aria-invalid={Boolean(formErrors.sleep_start)} disabled={saving} /><FieldError>{formErrors.sleep_start}</FieldError></Field><Field data-invalid={Boolean(formErrors.sleep_end)}><FieldLabel htmlFor="sleep-end">{t("remote.ends")}</FieldLabel><Input id="sleep-end" type="time" value={sleepEnd} onChange={(event) => setSleepEnd(event.target.value)} aria-invalid={Boolean(formErrors.sleep_end)} disabled={saving} /><FieldError>{formErrors.sleep_end}</FieldError></Field></div>
          </FieldGroup></div>
          <Separator /><SheetFooter className="flex-row justify-end"><Button variant="outline" onClick={() => setSheetOpen(false)} disabled={saving}>{t("common.cancel")}</Button><Button onClick={() => void saveSettings()} disabled={saving}>{saving && <Spinner data-icon="inline-start" />}{saving ? t("common.saving") : t("devices.saveChanges")}</Button></SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
