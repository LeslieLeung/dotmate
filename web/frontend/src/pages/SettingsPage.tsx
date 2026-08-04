import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { KeyRound, Pencil, Plus, RefreshCw, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";

import { LanguageSettingsCard } from "@/components/LanguageSettingsCard";
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
import { vendorCredentialHint } from "@/i18n/metadata";

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
  const { t } = useTranslation();
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
      if (!row.name.trim()) fields.name = t("settings.nameRequired");
      if (!row.vendor) fields.vendor = t("settings.vendorRequired");
      if (!row.api_key.trim()) fields.api_key = t("settings.apiKeyRequired");
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
      toast.error(error instanceof Error ? error.message : t("settings.addFailed"));
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
          t("settings.syncOneResult", {
            name: credential.name,
            created: result.sync.created,
            duplicates: result.sync.duplicates,
          })
        );
      } else {
        const result = await apiKeysApi.syncAll();
        const succeeded = result.results.filter((item) => item.status === "success").length;
        toast.success(t("settings.syncAllResult", { succeeded, total: result.results.length }));
      }
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("settings.syncFailed"));
    } finally {
      setSyncingId(null);
    }
  }

  async function handleRename() {
    if (!renaming || !renameValue.trim()) return;
    setRenameSaving(true);
    try {
      await apiKeysApi.rename(renaming.id, renameValue.trim());
      toast.success(t("settings.renamed"));
      setRenaming(null);
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("settings.renameFailed"));
    } finally {
      setRenameSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setDeleteSaving(true);
    try {
      await apiKeysApi.delete(deleting.id);
      toast.success(t("settings.deleted"));
      setDeleting(null);
      await loadData();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("settings.deleteFailed"));
    } finally {
      setDeleteSaving(false);
    }
  }

  async function handleSaveSettings() {
    const interval = Number(requestInterval);
    if (!Number.isFinite(interval) || interval <= 0 || interval > 60) {
      setIntervalError(t("settings.intervalValidation"));
      return;
    }
    setSavingSettings(true);
    try {
      await settingsApi.update({ request_interval: interval });
      toast.success(t("settings.saved"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("settings.saveFailed"));
    } finally {
      setSavingSettings(false);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold">{t("settings.title")}</h1>
          <p className="text-muted-foreground">{t("settings.description")}</p>
        </div>
        <LanguageSettingsCard />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold">{t("settings.title")}</h1>
          <p className="text-muted-foreground">{t("settings.description")}</p>
        </div>
        <LanguageSettingsCard />
        <Card>
          <CardHeader><CardTitle>{t("settings.unableToLoad")}</CardTitle><CardDescription>{t("auth.connectionHint")}</CardDescription></CardHeader>
          <CardContent><Button onClick={() => void loadData()}>{t("common.tryAgain")}</Button></CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{t("settings.title")}</h1>
        <p className="text-muted-foreground">{t("settings.description")}</p>
      </div>

      <LanguageSettingsCard />

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div><CardTitle>{t("settings.apiKeys")}</CardTitle><CardDescription>{t("settings.apiKeysDescription")}</CardDescription></div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void handleSync()} disabled={!credentials.some((c) => vendors.find((v) => v.id === c.vendor)?.supports_device_discovery) || syncingId !== null}>
                {syncingId === "all" ? <Spinner data-icon="inline-start" /> : <RefreshCw data-icon="inline-start" />}
                {t("settings.syncAll")}
              </Button>
              <Button onClick={openAddDialog}><Plus data-icon="inline-start" />{t("settings.addApiKeys")}</Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="overflow-x-auto p-0">
          {credentials.length ? (
            <Table>
              <TableHeader><TableRow><TableHead>{t("common.name")}</TableHead><TableHead>{t("common.vendor")}</TableHead><TableHead>{t("common.key")}</TableHead><TableHead>{t("settings.devices")}</TableHead><TableHead>{t("common.status")}</TableHead><TableHead className="text-right">{t("common.actions")}</TableHead></TableRow></TableHeader>
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
                    <TableCell><Badge variant="secondary">{t(`status.${credential.validation_status || "unverified"}`)}</Badge></TableCell>
                    <TableCell><div className="flex justify-end gap-1">
                      {canSync && (
                        <Button variant="ghost" size="icon-sm" aria-label={t("settings.syncAria", { name: credential.name })} onClick={() => void handleSync(credential)} disabled={syncingId !== null}>{syncingId === credential.id ? <Spinner /> : <RefreshCw />}</Button>
                      )}
                      <Button variant="ghost" size="icon-sm" aria-label={t("settings.renameAria", { name: credential.name })} onClick={() => { setRenaming(credential); setRenameValue(credential.name); }}><Pencil /></Button>
                      <Button variant="ghost" size="icon-sm" aria-label={t("settings.deleteAria", { name: credential.name })} onClick={() => setDeleting(credential)} disabled={credential.device_count > 0}><Trash2 /></Button>
                    </div></TableCell>
                  </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-center gap-3 p-10 text-center">
              <KeyRound />
              <div><p className="font-medium">{t("settings.noApiKeys")}</p><p className="text-sm text-muted-foreground">{t("settings.noApiKeysDescription")}</p></div>
              <Button onClick={openAddDialog}><Plus data-icon="inline-start" />{t("settings.addApiKeys")}</Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>{t("settings.requestRate")}</CardTitle><CardDescription>{t("settings.requestRateDescription")}</CardDescription></CardHeader>
        <CardContent>
          <FieldGroup>
            <Field data-invalid={Boolean(intervalError)}>
              <FieldLabel htmlFor="request-interval">{t("settings.requestInterval")}</FieldLabel>
              <Input id="request-interval" type="number" step="0.1" min="0.1" max="60" value={requestInterval} onChange={(event) => { setRequestInterval(event.target.value); setIntervalError(""); }} aria-invalid={Boolean(intervalError)} disabled={savingSettings} />
              <FieldDescription>{t("settings.requestIntervalDescription")}</FieldDescription><FieldError>{intervalError}</FieldError>
            </Field>
            <Button className="w-fit" onClick={() => void handleSaveSettings()} disabled={savingSettings}>{savingSettings && <Spinner data-icon="inline-start" />}{savingSettings ? t("common.saving") : t("settings.saveSettings")}</Button>
          </FieldGroup>
        </CardContent>
      </Card>

      <Dialog open={addOpen} onOpenChange={(open) => !adding && setAddOpen(open)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>{t("settings.addApiKeys")}</DialogTitle><DialogDescription>{t("settings.addDescription")}</DialogDescription></DialogHeader>
          {batchResults ? (
            <div className="flex flex-col gap-3">
              {batchResults.map((result) => (
                <Card key={result.index}>
                  <CardHeader><div className="flex items-start justify-between gap-3"><div><CardTitle>{result.name}</CardTitle><CardDescription>{result.vendor}</CardDescription></div><Badge variant={result.status === "success" ? "secondary" : "destructive"}>{t(`status.${result.status}`)}</Badge></div></CardHeader>
                  <CardContent className="text-sm text-muted-foreground">
                    {result.status === "success"
                      ? result.sync
                        ? t("settings.devicesAdded", { created: result.sync.created, duplicates: result.sync.duplicates })
                        : result.validation_status === "unverified"
                          ? t("settings.savedUnverified")
                          : t("settings.credentialSaved")
                      : result.error_code
                        ? t(`errors.${result.error_code}`, {
                            ...result.error_params,
                            defaultValue: t("errors.generic"),
                          })
                        : t("errors.generic")}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {credentialRows.map((row, index) => (
                <Card key={index}>
                  <CardHeader><div className="flex items-center justify-between"><CardTitle>{t("settings.credentialNumber", { count: index + 1 })}</CardTitle>{credentialRows.length > 1 && <Button variant="ghost" size="icon-sm" aria-label={t("settings.removeCredentialAria", { count: index + 1 })} onClick={() => setCredentialRows((current) => current.filter((_, rowIndex) => rowIndex !== index))}><X /></Button>}</div></CardHeader>
                  <CardContent><FieldGroup>
                    <Field data-invalid={Boolean(rowErrors[index]?.vendor)}><FieldLabel>{t("common.vendor")}*</FieldLabel><Select value={row.vendor} onValueChange={(value) => updateRow(index, "vendor", value)} disabled={adding}><SelectTrigger className="w-full" aria-invalid={Boolean(rowErrors[index]?.vendor)}><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{vendors.map((vendor) => <SelectItem key={vendor.id} value={vendor.id}>{vendor.label}</SelectItem>)}</SelectGroup></SelectContent></Select><FieldError>{rowErrors[index]?.vendor}</FieldError></Field>
                    <Field data-invalid={Boolean(rowErrors[index]?.name)}><FieldLabel>{t("common.name")}*</FieldLabel><Input value={row.name} onChange={(event) => updateRow(index, "name", event.target.value)} placeholder={t("settings.namePlaceholder")} aria-invalid={Boolean(rowErrors[index]?.name)} disabled={adding} /><FieldError>{rowErrors[index]?.name}</FieldError></Field>
                    <Field data-invalid={Boolean(rowErrors[index]?.api_key)}><FieldLabel>{t("common.apiKey")}*</FieldLabel><Input type="password" value={row.api_key} onChange={(event) => updateRow(index, "api_key", event.target.value)} placeholder={t("settings.enterApiKey")} autoComplete="new-password" aria-invalid={Boolean(rowErrors[index]?.api_key)} disabled={adding} /><FieldDescription>{(() => { const vendor = vendors.find((item) => item.id === row.vendor); return vendor ? vendorCredentialHint(t, vendor) : ""; })()}</FieldDescription><FieldError>{rowErrors[index]?.api_key}</FieldError></Field>
                  </FieldGroup></CardContent>
                </Card>
              ))}
              <Button variant="outline" className="w-fit" onClick={() => setCredentialRows((current) => [...current, emptyCredential()])} disabled={adding}><Plus data-icon="inline-start" />{t("settings.addAnother")}</Button>
            </div>
          )}
          <DialogFooter>
            {batchResults ? <Button onClick={() => setAddOpen(false)}>{t("common.done")}</Button> : <><Button variant="outline" onClick={() => setAddOpen(false)} disabled={adding}>{t("common.cancel")}</Button><Button onClick={() => void handleAddCredentials()} disabled={adding}>{adding && <Spinner data-icon="inline-start" />}{adding ? t("common.saving") : t("settings.addKeys", { count: credentialRows.length })}</Button></>}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(renaming)} onOpenChange={(open) => !open && !renameSaving && setRenaming(null)}>
        <DialogContent><DialogHeader><DialogTitle>{t("settings.renameTitle")}</DialogTitle><DialogDescription>{t("settings.renameDescription")}</DialogDescription></DialogHeader><Field><FieldLabel htmlFor="credential-name">{t("common.name")}</FieldLabel><Input id="credential-name" value={renameValue} onChange={(event) => setRenameValue(event.target.value)} disabled={renameSaving} /></Field><DialogFooter><Button variant="outline" onClick={() => setRenaming(null)} disabled={renameSaving}>{t("common.cancel")}</Button><Button onClick={() => void handleRename()} disabled={renameSaving || !renameValue.trim()}>{renameSaving && <Spinner data-icon="inline-start" />}{t("common.save")}</Button></DialogFooter></DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleting)} onOpenChange={(open) => !open && !deleteSaving && setDeleting(null)}>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{t("settings.deleteTitle", { name: deleting?.name })}</AlertDialogTitle><AlertDialogDescription>{t("settings.deleteDescription")}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel disabled={deleteSaving}>{t("common.cancel")}</AlertDialogCancel><AlertDialogAction variant="destructive" onClick={(event) => { event.preventDefault(); void handleDelete(); }} disabled={deleteSaving}>{deleteSaving && <Spinner data-icon="inline-start" />}{t("common.delete")}</AlertDialogAction></AlertDialogFooter></AlertDialogContent>
      </AlertDialog>
      <Separator />
    </div>
  );
}
