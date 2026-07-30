import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Monitor, Pencil, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";

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
  EmptyContent,
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
  apiKeysApi,
  deviceModelsApi,
  devicesApi,
  vendorsApi,
  type ApiCredential,
  type Device,
  type DeviceModel,
  type Vendor,
} from "@/lib/api";
import {
  formatStatusTimestamp,
  statusRefreshCompleted,
  wait,
} from "@/lib/device-status";

export function DevicesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [devices, setDevices] = useState<Device[]>([]);
  const [credentials, setCredentials] = useState<ApiCredential[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [deviceModels, setDeviceModels] = useState<DeviceModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingDevice, setEditingDevice] = useState<Device | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Device | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [refreshingStatuses, setRefreshingStatuses] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const [formVendor, setFormVendor] = useState("");
  const [formName, setFormName] = useState("");
  const [formDeviceId, setFormDeviceId] = useState("");
  const [formCredentialId, setFormCredentialId] = useState("");
  const [formDeviceModel, setFormDeviceModel] = useState("");
  const [formBatteryIcon, setFormBatteryIcon] = useState(false);
  const [formBatteryPercent, setFormBatteryPercent] = useState(false);
  const [formRefreshTime, setFormRefreshTime] = useState(false);

  const loadDevices = useCallback(async () => {
    setLoadFailed(false);
    try {
      const [deviceList, credentialList, vendorList, modelList] = await Promise.all([
        devicesApi.list(),
        apiKeysApi.list(),
        vendorsApi.list(),
        deviceModelsApi.list(),
      ]);
      setDevices(deviceList);
      setCredentials(credentialList);
      setVendors(vendorList);
      setDeviceModels(modelList);
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDevices();
  }, [loadDevices]);

  const selectedModel = useMemo(
    () => deviceModels.find((model) => model.id === formDeviceModel) ?? null,
    [deviceModels, formDeviceModel]
  );

  const vendorCredentials = useMemo(
    () =>
      credentials.filter((credential) =>
        editingDevice
          ? credential.vendor === editingDevice.vendor
          : !formVendor || credential.vendor === formVendor
      ),
    [credentials, editingDevice, formVendor]
  );

  const vendorModels = useMemo(
    () =>
      deviceModels.filter((model) =>
        editingDevice
          ? model.vendor_id === editingDevice.vendor
          : !formVendor || model.vendor_id === formVendor
      ),
    [deviceModels, editingDevice, formVendor]
  );

  function openCreateDialog() {
    setEditingDevice(null);
    const defaultVendor = vendors[0]?.id ?? "";
    const modelsForVendor = deviceModels.filter((model) => model.vendor_id === defaultVendor);
    const credsForVendor = credentials.filter((credential) => credential.vendor === defaultVendor);
    setFormVendor(defaultVendor);
    setFormName("");
    setFormDeviceId("");
    setFormCredentialId(credsForVendor.length === 1 ? String(credsForVendor[0].id) : "");
    setFormDeviceModel(modelsForVendor[0]?.id ?? "");
    setFormBatteryIcon(false);
    setFormBatteryPercent(false);
    setFormRefreshTime(false);
    setFormErrors({});
    setDialogOpen(true);
  }

  function openEditDialog(device: Device) {
    setEditingDevice(device);
    setFormVendor(device.vendor);
    setFormName(device.name);
    setFormDeviceId(device.device_id);
    setFormCredentialId(String(device.api_credential_id));
    setFormDeviceModel(device.device_model);
    setFormBatteryIcon(device.show_battery_icon);
    setFormBatteryPercent(device.show_battery_percentage);
    setFormRefreshTime(device.show_refresh_time);
    setFormErrors({});
    setDialogOpen(true);
  }

  function handleVendorChange(vendorId: string) {
    setFormVendor(vendorId);
    const modelsForVendor = deviceModels.filter((model) => model.vendor_id === vendorId);
    const credsForVendor = credentials.filter((credential) => credential.vendor === vendorId);
    setFormDeviceModel(modelsForVendor[0]?.id ?? "");
    setFormCredentialId(credsForVendor.length === 1 ? String(credsForVendor[0].id) : "");
    setFormBatteryIcon(false);
    setFormBatteryPercent(false);
    setFormErrors((current) => ({
      ...current,
      vendor: "",
      api_credential_id: "",
      device_model: "",
    }));
  }

  async function handleSave() {
    const errors: Record<string, string> = {};
    if (!editingDevice && !formVendor) errors.vendor = "Vendor is required";
    if (!formName.trim()) errors.name = "Name is required";
    if (!formDeviceId.trim()) errors.device_id = "Device ID is required";
    if (!formCredentialId) errors.api_credential_id = "API key is required";
    if (!editingDevice && !formDeviceModel) errors.device_model = "Device model is required";
    setFormErrors(errors);
    if (Object.keys(errors).length || saving) return;

    setSaving(true);
    const supportsBattery = selectedModel?.supports_battery_overlay ?? false;
    try {
      if (editingDevice) {
        await devicesApi.update(editingDevice.id, {
          name: formName.trim(),
          device_id: formDeviceId.trim(),
          api_credential_id: Number(formCredentialId),
          show_battery_icon: supportsBattery ? formBatteryIcon : false,
          show_battery_percentage: supportsBattery ? formBatteryPercent : false,
          show_refresh_time: formRefreshTime,
        });
        toast.success("Device updated");
      } else {
        await devicesApi.create({
          name: formName.trim(),
          device_id: formDeviceId.trim(),
          api_credential_id: Number(formCredentialId),
          device_model: formDeviceModel,
          show_battery_icon: supportsBattery ? formBatteryIcon : false,
          show_battery_percentage: supportsBattery ? formBatteryPercent : false,
          show_refresh_time: formRefreshTime,
        });
        toast.success("Device created");
      }
      setDialogOpen(false);
      await loadDevices();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save device");
    } finally {
      setSaving(false);
    }
  }

  const search = searchParams.get("q") ?? "";
  const vendorFilter = searchParams.get("vendor") ?? "all";
  const modelFilter = searchParams.get("device_model") ?? "all";
  const credentialFilter = searchParams.get("api_key_id") ?? "all";
  const visibleDevices = devices.filter((device) => {
    const query = search.trim().toLowerCase();
    if (query && !device.name.toLowerCase().includes(query) && !device.device_id.toLowerCase().includes(query)) return false;
    if (vendorFilter !== "all" && device.vendor !== vendorFilter) return false;
    if (modelFilter !== "all" && device.device_model !== modelFilter) return false;
    if (credentialFilter !== "all" && String(device.api_credential_id) !== credentialFilter) return false;
    return true;
  });

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (!value || value === "all") next.delete(key);
    else next.set(key, value);
    setSearchParams(next);
  }

  async function handleDelete() {
    if (!deleteConfirm || deleting) return;
    setDeleting(true);
    try {
      await devicesApi.delete(deleteConfirm.id);
      toast.success("Device deleted");
      setDeleteConfirm(null);
      await loadDevices();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete device");
    } finally {
      setDeleting(false);
    }
  }

  async function handleRefreshStatuses() {
    if (refreshingStatuses) return;
    setRefreshingStatuses(true);
    try {
      const request = await devicesApi.refreshAllStatuses();
      if (!request.queued) {
        toast.info("No devices support status refresh");
        return;
      }
      const deadline = Date.now() + 60_000;
      while (Date.now() < deadline) {
        await wait(2_000);
        const latest = await devicesApi.list();
        setDevices(latest);
        const targets = latest.filter((device) =>
          device.vendor_capabilities.includes("status")
        );
        if (
          targets.length > 0
          && targets.every(
            (device) =>
              device.status_policy
              && statusRefreshCompleted(device.status_policy, request.requested_at)
          )
        ) {
          const failures = targets.filter((device) => device.status_policy.last_error).length;
          if (failures) toast.error(`${failures} device ${failures === 1 ? "status" : "statuses"} could not be refreshed`);
          else toast.success("Device statuses refreshed");
          return;
        }
      }
      toast.info("Refresh is continuing in the background");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to refresh statuses");
    } finally {
      setRefreshingStatuses(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-14 w-64" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Devices</h1>
          <p className="text-muted-foreground">Manage your e-ink devices</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => void handleRefreshStatuses()}
            disabled={!devices.length || refreshingStatuses}
          >
            {refreshingStatuses
              ? <Spinner data-icon="inline-start" />
              : <RefreshCw data-icon="inline-start" />}
            {refreshingStatuses ? "Refreshing..." : "Refresh Statuses"}
          </Button>
          <Button onClick={openCreateDialog} disabled={!credentials.length}>
            <Plus data-icon="inline-start" />
            Add Device
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          <FieldGroup className="grid gap-4 md:grid-cols-4">
            <Field>
              <FieldLabel htmlFor="device-search">Search</FieldLabel>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input id="device-search" className="pl-8" value={search} onChange={(event) => updateFilter("q", event.target.value)} placeholder="Name or device ID" />
              </div>
            </Field>
            <Field>
              <FieldLabel>Vendor</FieldLabel>
              <Select value={vendorFilter} onValueChange={(value) => updateFilter("vendor", value)}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="all">All vendors</SelectItem>
                    {vendors.map((vendor) => (
                      <SelectItem key={vendor.id} value={vendor.id}>{vendor.label}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>Model</FieldLabel>
              <Select value={modelFilter} onValueChange={(value) => updateFilter("device_model", value)}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="all">All models</SelectItem>
                    {deviceModels
                      .filter((model) => vendorFilter === "all" || model.vendor_id === vendorFilter)
                      .map((model) => (
                        <SelectItem key={model.id} value={model.id}>{model.label}</SelectItem>
                      ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>API Key</FieldLabel>
              <Select value={credentialFilter} onValueChange={(value) => updateFilter("api_key_id", value)}>
                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="all">All API keys</SelectItem>
                    {credentials
                      .filter((credential) => vendorFilter === "all" || credential.vendor === vendorFilter)
                      .map((credential) => (
                        <SelectItem key={credential.id} value={String(credential.id)}>{credential.name}</SelectItem>
                      ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          </FieldGroup>
        </CardContent>
      </Card>

      {loadFailed ? (
        <Card>
          <CardHeader>
            <CardTitle>Unable to load devices</CardTitle>
            <CardDescription>Check the server connection and try again.</CardDescription>
          </CardHeader>
          <CardContent><Button onClick={() => void loadDevices()}>Try Again</Button></CardContent>
        </Card>
      ) : devices.length === 0 ? (
        <Card>
          <CardContent>
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><Monitor /></EmptyMedia>
                <EmptyTitle>No devices yet</EmptyTitle>
                <EmptyDescription>Add your first e-ink device to create schedules.</EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button onClick={openCreateDialog} disabled={!credentials.length}>
                  <Plus data-icon="inline-start" />
                  Add Device
                </Button>
              </EmptyContent>
            </Empty>
          </CardContent>
        </Card>
      ) : visibleDevices.length === 0 ? (
        <Card>
          <CardContent>
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><Search /></EmptyMedia>
                <EmptyTitle>No matching devices</EmptyTitle>
                <EmptyDescription>Change the search or filters to see more devices.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Configured devices</CardTitle>
            <CardDescription>Select a device to manage its schedules.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Device ID</TableHead>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead>Resolution</TableHead>
                  <TableHead>API Key</TableHead>
                  <TableHead>Live Status</TableHead>
                  <TableHead>Schedules</TableHead>
                  <TableHead>Overlays</TableHead>
                  <TableHead className="w-24 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleDevices.map((device) => {
                  const overlays = [
                    device.show_battery_icon && "Battery",
                    device.show_battery_percentage && "Percentage",
                    device.show_refresh_time && "Refresh time",
                  ].filter(Boolean) as string[];
                  return (
                    <TableRow key={device.id}>
                      <TableCell className="font-medium">
                        <Link to={`/devices/${device.id}`} className="text-primary hover:underline">
                          {device.name}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{device.device_id}</TableCell>
                      <TableCell><Badge variant="secondary">{device.vendor_label || device.vendor}</Badge></TableCell>
                      <TableCell>{device.device_model_label}</TableCell>
                      <TableCell className="font-mono text-sm">
                        {device.display_width}×{device.display_height}
                      </TableCell>
                      <TableCell>{device.api_credential_name}</TableCell>
                      <TableCell>
                        {device.vendor_capabilities.includes("status") ? (
                          <div className="flex min-w-44 flex-col gap-1 text-sm">
                            <div className="flex flex-wrap items-center gap-1">
                              <Badge
                                variant={device.status_policy?.state === "error" ? "destructive" : "secondary"}
                              >
                                {device.status_policy?.state ?? "pending"}
                              </Badge>
                              <span>{device.remote_status?.current || "Waiting for status"}</span>
                            </div>
                            {device.remote_status && (
                              <span className="text-muted-foreground">
                                {device.remote_status.battery || "Battery —"} · {device.remote_status.wifi || "Wi-Fi —"}
                              </span>
                            )}
                            <span className="text-xs text-muted-foreground">
                              Updated {formatStatusTimestamp(device.status_policy?.last_success_at ?? null)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-sm text-muted-foreground">Status unavailable</span>
                        )}
                      </TableCell>
                      <TableCell>{device.schedules.length}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {overlays.length
                            ? overlays.map((overlay) => <Badge key={overlay} variant="secondary">{overlay}</Badge>)
                            : <span className="text-sm text-muted-foreground">None</span>}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon-sm" aria-label={`Edit ${device.name}`} onClick={() => openEditDialog(device)}>
                            <Pencil />
                          </Button>
                          <Button variant="ghost" size="icon-sm" aria-label={`Delete ${device.name}`} onClick={() => setDeleteConfirm(device)}>
                            <Trash2 />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={(open) => !saving && setDialogOpen(open)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingDevice ? "Edit Device" : "Add Device"}</DialogTitle>
            <DialogDescription>
              {editingDevice
                ? "Update device settings. Vendor and model cannot be changed."
                : "Choose a vendor, credential, and device model."}
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            {!editingDevice && (
              <Field data-invalid={Boolean(formErrors.vendor)}>
                <FieldLabel>Vendor*</FieldLabel>
                <Select value={formVendor} onValueChange={handleVendorChange} disabled={saving}>
                  <SelectTrigger className="w-full" aria-invalid={Boolean(formErrors.vendor)}>
                    <SelectValue placeholder="Select a vendor" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {vendors.map((vendor) => (
                        <SelectItem key={vendor.id} value={vendor.id}>{vendor.label}</SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <FieldError>{formErrors.vendor}</FieldError>
              </Field>
            )}
            <Field data-invalid={Boolean(formErrors.api_credential_id)}>
              <FieldLabel>API Key*</FieldLabel>
              <Select
                value={formCredentialId}
                onValueChange={(value) => {
                  setFormCredentialId(value);
                  setFormErrors((current) => ({ ...current, api_credential_id: "" }));
                }}
                disabled={saving}
              >
                <SelectTrigger className="w-full" aria-invalid={Boolean(formErrors.api_credential_id)}>
                  <SelectValue placeholder="Select an API key" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {vendorCredentials.map((credential) => (
                      <SelectItem key={credential.id} value={String(credential.id)}>
                        {credential.name} ({credential.vendor_label || credential.vendor})
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <FieldDescription>
                {editingDevice
                  ? "Devices can only be reassigned within the same vendor."
                  : "Credentials are scoped to the selected vendor."}
              </FieldDescription>
              <FieldError>{formErrors.api_credential_id}</FieldError>
            </Field>
            <Field data-invalid={Boolean(formErrors.device_model)}>
              <FieldLabel>Device Model*</FieldLabel>
              {editingDevice ? (
                <>
                  <Input value={editingDevice.device_model_label} disabled />
                  <FieldDescription>
                    {editingDevice.display_width}×{editingDevice.display_height}
                    {" · "}
                    {editingDevice.display_capabilities.includes("text") ? "Text + image" : "Image only"}
                  </FieldDescription>
                </>
              ) : (
                <>
                  <Select
                    value={formDeviceModel}
                    onValueChange={(value) => {
                      setFormDeviceModel(value);
                      setFormBatteryIcon(false);
                      setFormBatteryPercent(false);
                      setFormErrors((current) => ({ ...current, device_model: "" }));
                    }}
                    disabled={saving || !formVendor}
                  >
                    <SelectTrigger className="w-full" aria-invalid={Boolean(formErrors.device_model)}>
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {vendorModels.map((model) => (
                          <SelectItem key={model.id} value={model.id}>
                            {model.label} ({model.width}×{model.height})
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                  {selectedModel && (
                    <FieldDescription>{selectedModel.description}</FieldDescription>
                  )}
                  <FieldError>{formErrors.device_model}</FieldError>
                </>
              )}
            </Field>
            <Field data-invalid={Boolean(formErrors.name)}>
              <FieldLabel htmlFor="device-name">Name*</FieldLabel>
              <Input id="device-name" value={formName} onChange={(event) => setFormName(event.target.value)} aria-invalid={Boolean(formErrors.name)} disabled={saving} />
              <FieldError>{formErrors.name}</FieldError>
            </Field>
            <Field data-invalid={Boolean(formErrors.device_id)}>
              <FieldLabel htmlFor="device-id">
                {selectedModel?.device_id_label || editingDevice?.device_model_label || "Device ID"}*
              </FieldLabel>
              <Input
                id="device-id"
                value={formDeviceId}
                onChange={(event) => setFormDeviceId(event.target.value)}
                placeholder={selectedModel?.device_id_example}
                aria-invalid={Boolean(formErrors.device_id)}
                disabled={saving}
              />
              <FieldError>{formErrors.device_id}</FieldError>
            </Field>
            {(selectedModel?.supports_battery_overlay
              || editingDevice?.display_capabilities.includes("battery_overlay")) && (
              <>
                <Field orientation="horizontal">
                  <FieldContent>
                    <FieldLabel htmlFor="battery-icon">Battery Icon</FieldLabel>
                    <FieldDescription>Show a battery symbol on image-based content.</FieldDescription>
                  </FieldContent>
                  <Switch id="battery-icon" checked={formBatteryIcon} onCheckedChange={setFormBatteryIcon} disabled={saving} />
                </Field>
                <Field orientation="horizontal">
                  <FieldContent>
                    <FieldLabel htmlFor="battery-percent">Battery Percentage</FieldLabel>
                  </FieldContent>
                  <Switch id="battery-percent" checked={formBatteryPercent} onCheckedChange={setFormBatteryPercent} disabled={saving} />
                </Field>
              </>
            )}
            {editingDevice
              && !editingDevice.display_capabilities.includes("battery_overlay")
              && (editingDevice.show_battery_icon || editingDevice.show_battery_percentage) && (
              <FieldDescription>
                Battery overlays are not supported on this model and will be cleared on save.
              </FieldDescription>
            )}
            <Field orientation="horizontal">
              <FieldContent>
                <FieldLabel htmlFor="refresh-time">Refresh Time</FieldLabel>
              </FieldContent>
              <Switch id="refresh-time" checked={formRefreshTime} onCheckedChange={setFormRefreshTime} disabled={saving} />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</Button>
            <Button onClick={() => void handleSave()} disabled={saving}>
              {saving && <Spinner data-icon="inline-start" />}
              {saving ? "Saving..." : editingDevice ? "Save Changes" : "Create Device"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleteConfirm)} onOpenChange={(open) => !open && !deleting && setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {deleteConfirm?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              All schedules for this device will also be deleted. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={(event) => {
              event.preventDefault();
              void handleDelete();
            }} disabled={deleting}>
              {deleting && <Spinner data-icon="inline-start" />}
              {deleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
