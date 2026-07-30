import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { KeyRound, Pencil, Plus, RefreshCw, Trash2, X } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
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
  settingsApi,
  vendorsApi,
  type ApiCredential,
  type ApiCredentialBatchResult,
  type Vendor,
} from "@/lib/api";

interface CredentialRow {
  name: string;
  vendor: string;
  api_key: string;
}

const emptyCredential = (): CredentialRow => ({
  name: "",
  vendor: "mindreset",
  api_key: "",
});

export function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [credentials, setCredentials] = useState<ApiCredential[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [requestInterval, setRequestInterval] = useState("1.0");
  const [intervalError, setIntervalError] = useState("");
  const [savingSettings, setSavingSettings] = useState(false);
  const [syncingId, setSyncingId] = useState<number | "all" | null>(null);

  const [addOpen, setAddOpen] = useState(false);
  const [credentialRows, setCredentialRows] = useState<CredentialRow[]>([emptyCredential()]);
  const [rowErrors, setRowErrors] = useState<Record<number, Record<string, string>>>({});
  const [batchResults, setBatchResults] = useState<ApiCredentialBatchResult[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [renaming, setRenaming] = useState<ApiCredential | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameSaving, setRenameSaving] = useState(false);
  const [deleting, setDeleting] = useState<ApiCredential | null>(null);
  const [deleteSaving, setDeleteSaving] = useState(false);

  const loadData = useCallback(async () => {
    setLoadError(false);
    try {
      const [settings, keys, vendorList] = await Promise.all([
        settingsApi.get(),
        apiKeysApi.list(),
        vendorsApi.list(),
      ]);
      setRequestInterval(String(settings.request_interval));
      setCredentials(keys);
      setVendors(vendorList);
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  function openAddDialog() {
    setCredentialRows([emptyCredential()]);
    setRowErrors({});
    setBatchResults(null);
    setAddOpen(true);
  }

  function updateRow(index: number, field: keyof CredentialRow, value: string) {
    setCredentialRows((current) =>
      current.map((row, rowIndex) => rowIndex === index ? { ...row, [field]: value } : row)
    );
    setRowErrors((current) => {
      const next = { ...current };
      if (next[index]) next[index] = { ...next[index], [field]: "" };
      return next;
    });
  }

  async function handleAddCredentials() {
    const errors: Record<number, Record<string, string>> = {};
    credentialRows.forEach((row, index) => {
      const fields: Record<string, string> = {};
      if (!row.name.trim()) fields.name = "Name is required";
      if (!row.vendor) fields.vendor = "Vendor is required";
      if (!row.api_key.trim()) fields.api_key = "API key is required";
      if (Object.keys(fields).length) errors[index] = fields;
    });
    setRowErrors(errors);
    if (Object.keys(errors).length) return;

    setAdding(true);
    try {
      const response = await apiKeysApi.createBatch(
        credentialRows.map((row) => ({
          name: row.name.trim(),
          vendor: row.vendor,
          api_key: row.api_key.trim(),
        }))
      );
      setBatchResults(response.results);
      if (response.results.some((result) => result.status === "success")) await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to add API keys");
    } finally {
      setAdding(false);
    }
  }

  async function handleSync(credential?: ApiCredential) {
    setSyncingId(credential?.id ?? "all");
    try {
      if (credential) {
        const result = await apiKeysApi.sync(credential.id);
        toast.success(
          `${credential.name}: ${result.sync.created} added, ${result.sync.duplicates} duplicates`
        );
      } else {
        const result = await apiKeysApi.syncAll();
        const succeeded = result.results.filter((item) => item.status === "success").length;
        toast.success(`Synced ${succeeded} of ${result.results.length} API keys`);
      }
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Sync failed");
    } finally {
      setSyncingId(null);
    }
  }

  async function handleRename() {
    if (!renaming || !renameValue.trim()) return;
    setRenameSaving(true);
    try {
      await apiKeysApi.rename(renaming.id, renameValue.trim());
      toast.success("API key renamed");
      setRenaming(null);
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Rename failed");
    } finally {
      setRenameSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setDeleteSaving(true);
    try {
      await apiKeysApi.delete(deleting.id);
      toast.success("API key deleted");
      setDeleting(null);
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setDeleteSaving(false);
    }
  }

  async function handleSaveSettings() {
    const interval = Number(requestInterval);
    if (!Number.isFinite(interval) || interval <= 0 || interval > 60) {
      setIntervalError("Enter a value greater than 0 and no more than 60 seconds");
      return;
    }
    setSavingSettings(true);
    try {
      await settingsApi.update({ request_interval: interval });
      toast.success("Settings saved and scheduler reloaded");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save settings");
    } finally {
      setSavingSettings(false);
    }
  }

  if (loading) {
    return <div className="flex flex-col gap-6"><Skeleton className="h-14 w-64" /><Skeleton className="h-72 w-full" /></div>;
  }

  if (loadError) {
    return (
      <Card>
        <CardHeader><CardTitle>Unable to load settings</CardTitle><CardDescription>Check the server connection and try again.</CardDescription></CardHeader>
        <CardContent><Button onClick={() => void loadData()}>Try Again</Button></CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground">Manage vendor credentials and global behavior</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div><CardTitle>API Keys</CardTitle><CardDescription>Credentials used to discover and control devices.</CardDescription></div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void handleSync()} disabled={!credentials.some((c) => vendors.find((v) => v.id === c.vendor)?.supports_device_discovery) || syncingId !== null}>
                {syncingId === "all" ? <Spinner data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />}
                Sync All
              </Button>
              <Button onClick={openAddDialog}><Plus data-icon="inline-start" />Add API Keys</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {credentials.length ? (
            <Table>
              <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Vendor</TableHead><TableHead>Key</TableHead><TableHead>Devices</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Actions</TableHead></TableRow></TableHeader>
              <TableBody>
                {credentials.map((credential) => {
                  const vendor = vendors.find((item) => item.id === credential.vendor);
                  const canSync = Boolean(vendor?.supports_device_discovery);
                  return (
                  <TableRow key={credential.id}>
                    <TableCell className="font-medium">{credential.name}</TableCell>
                    <TableCell><Badge variant="secondary">{credential.vendor_label || credential.vendor}</Badge></TableCell>
                    <TableCell className="font-mono text-sm">{credential.masked_key}</TableCell>
                    <TableCell><Button variant="link" asChild className="px-0"><Link to={`/devices?api_key_id=${credential.id}`}>{credential.device_count}</Link></Button></TableCell>
                    <TableCell><Badge variant="secondary">{credential.validation_status || "unverified"}</Badge></TableCell>
                    <TableCell><div className="flex justify-end gap-1">
                      {canSync && (
                        <Button variant="ghost" size="icon-sm" aria-label={`Sync ${credential.name}`} onClick={() => void handleSync(credential)} disabled={syncingId !== null}>{syncingId === credential.id ? <Spinner /> : <RefreshCw />}</Button>
                      )}
                      <Button variant="ghost" size="icon-sm" aria-label={`Rename ${credential.name}`} onClick={() => { setRenaming(credential); setRenameValue(credential.name); }}><Pencil /></Button>
                      <Button variant="ghost" size="icon-sm" aria-label={`Delete ${credential.name}`} onClick={() => setDeleting(credential)} disabled={credential.device_count > 0}><Trash2 /></Button>
                    </div></TableCell>
                  </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-center gap-3 p-10 text-center">
              <KeyRound />
              <div><p className="font-medium">No API keys</p><p className="text-sm text-muted-foreground">Add one or more credentials to discover devices.</p></div>
              <Button onClick={openAddDialog}><Plus data-icon="inline-start" />Add API Keys</Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Request Rate</CardTitle><CardDescription>Minimum delay applied independently to each API key.</CardDescription></CardHeader>
        <CardContent>
          <FieldGroup>
            <Field data-invalid={Boolean(intervalError)}>
              <FieldLabel htmlFor="request-interval">Request Interval (seconds)</FieldLabel>
              <Input id="request-interval" type="number" step="0.1" min="0.1" max="60" value={requestInterval} onChange={(event) => { setRequestInterval(event.target.value); setIntervalError(""); }} aria-invalid={Boolean(intervalError)} disabled={savingSettings} />
              <FieldDescription>Use a conservative interval to stay within vendor rate limits.</FieldDescription><FieldError>{intervalError}</FieldError>
            </Field>
            <Button className="w-fit" onClick={() => void handleSaveSettings()} disabled={savingSettings}>{savingSettings && <Spinner data-icon="inline-start" />}{savingSettings ? "Saving..." : "Save Settings"}</Button>
          </FieldGroup>
        </CardContent>
      </Card>

      <Dialog open={addOpen} onOpenChange={(open) => !adding && setAddOpen(open)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>Add API Keys</DialogTitle><DialogDescription>Add several vendor credentials in one batch. Valid rows are saved even if another row fails.</DialogDescription></DialogHeader>
          {batchResults ? (
            <div className="flex flex-col gap-3">
              {batchResults.map((result) => (
                <Card key={result.index}>
                  <CardHeader><div className="flex items-start justify-between gap-3"><div><CardTitle>{result.name}</CardTitle><CardDescription>{result.vendor}</CardDescription></div><Badge variant={result.status === "success" ? "secondary" : "destructive"}>{result.status}</Badge></div></CardHeader>
                  <CardContent className="text-sm text-muted-foreground">
                    {result.status === "success"
                      ? result.sync
                        ? `${result.sync.created} devices added, ${result.sync.duplicates} duplicates`
                        : result.validation_status === "unverified"
                          ? "Saved without remote validation. Add devices manually from the Devices page."
                          : "Credential saved."
                      : result.error}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {credentialRows.map((row, index) => (
                <Card key={index}>
                  <CardHeader><div className="flex items-center justify-between"><CardTitle>Credential {index + 1}</CardTitle>{credentialRows.length > 1 && <Button variant="ghost" size="icon-sm" aria-label={`Remove credential ${index + 1}`} onClick={() => setCredentialRows((current) => current.filter((_, rowIndex) => rowIndex !== index))}><X /></Button>}</div></CardHeader>
                  <CardContent><FieldGroup>
                    <Field data-invalid={Boolean(rowErrors[index]?.vendor)}><FieldLabel>Vendor*</FieldLabel><Select value={row.vendor} onValueChange={(value) => updateRow(index, "vendor", value)} disabled={adding}><SelectTrigger className="w-full" aria-invalid={Boolean(rowErrors[index]?.vendor)}><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{vendors.map((vendor) => <SelectItem key={vendor.id} value={vendor.id}>{vendor.label}</SelectItem>)}</SelectGroup></SelectContent></Select><FieldError>{rowErrors[index]?.vendor}</FieldError></Field>
                    <Field data-invalid={Boolean(rowErrors[index]?.name)}><FieldLabel>Name*</FieldLabel><Input value={row.name} onChange={(event) => updateRow(index, "name", event.target.value)} placeholder="e.g. Personal" aria-invalid={Boolean(rowErrors[index]?.name)} disabled={adding} /><FieldError>{rowErrors[index]?.name}</FieldError></Field>
                    <Field data-invalid={Boolean(rowErrors[index]?.api_key)}><FieldLabel>API Key*</FieldLabel><Input type="password" value={row.api_key} onChange={(event) => updateRow(index, "api_key", event.target.value)} placeholder="Enter API key" autoComplete="new-password" aria-invalid={Boolean(rowErrors[index]?.api_key)} disabled={adding} /><FieldDescription>{vendors.find((vendor) => vendor.id === row.vendor)?.credential_hint}</FieldDescription><FieldError>{rowErrors[index]?.api_key}</FieldError></Field>
                  </FieldGroup></CardContent>
                </Card>
              ))}
              <Button variant="outline" className="w-fit" onClick={() => setCredentialRows((current) => [...current, emptyCredential()])} disabled={adding}><Plus data-icon="inline-start" />Add Another</Button>
            </div>
          )}
          <DialogFooter>
            {batchResults ? <Button onClick={() => setAddOpen(false)}>Done</Button> : <><Button variant="outline" onClick={() => setAddOpen(false)} disabled={adding}>Cancel</Button><Button onClick={() => void handleAddCredentials()} disabled={adding}>{adding && <Spinner data-icon="inline-start" />}{adding ? "Saving..." : `Add ${credentialRows.length} ${credentialRows.length === 1 ? "Key" : "Keys"}`}</Button></>}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(renaming)} onOpenChange={(open) => !open && !renameSaving && setRenaming(null)}>
        <DialogContent><DialogHeader><DialogTitle>Rename API Key</DialogTitle><DialogDescription>The stored credential is unchanged.</DialogDescription></DialogHeader><Field><FieldLabel htmlFor="credential-name">Name</FieldLabel><Input id="credential-name" value={renameValue} onChange={(event) => setRenameValue(event.target.value)} disabled={renameSaving} /></Field><DialogFooter><Button variant="outline" onClick={() => setRenaming(null)} disabled={renameSaving}>Cancel</Button><Button onClick={() => void handleRename()} disabled={renameSaving || !renameValue.trim()}>{renameSaving && <Spinner data-icon="inline-start" />}Save</Button></DialogFooter></DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && !deleteSaving && setDeleting(null)}>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Delete {deleting?.name}?</AlertDialogTitle><AlertDialogDescription>This removes the stored API key. Keys with devices cannot be deleted.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel disabled={deleteSaving}>Cancel</AlertDialogCancel><AlertDialogAction variant="destructive" onClick={(event) => { event.preventDefault(); void handleDelete(); }} disabled={deleteSaving}>{deleteSaving && <Spinner data-icon="inline-start" />}Delete</AlertDialogAction></AlertDialogFooter></AlertDialogContent>
      </AlertDialog>
      <Separator />
    </div>
  );
}
