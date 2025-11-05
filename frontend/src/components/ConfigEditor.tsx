import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ViewParamsForm } from "./ViewParamsForm";
import { PreviewPanel } from "./PreviewPanel";
import { apiClient } from "@/api/client";
import { Config, Device, Schedule, ViewTypeInfo } from "@/types";
import { Loader2, Plus, Trash2, Save } from "lucide-react";

export function ConfigEditor() {
  const [config, setConfig] = useState<Config | null>(null);
  const [viewTypes, setViewTypes] = useState<ViewTypeInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDeviceIndex, setSelectedDeviceIndex] = useState(0);
  const [selectedScheduleIndex, setSelectedScheduleIndex] = useState(0);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [configData, viewTypesData] = await Promise.all([
        apiClient.getConfig(),
        apiClient.getViewTypes(),
      ]);
      setConfig(configData);
      setViewTypes(viewTypesData);

      // Initialize with empty device if none exist
      if (!configData.devices || configData.devices.length === 0) {
        setConfig({
          ...configData,
          devices: [{
            name: "Device 1",
            device_id: "",
            schedules: []
          }]
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration");
    } finally {
      setLoading(false);
    }
  };

  const saveConfig = async () => {
    if (!config) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.saveConfig(config);
      alert("Configuration saved successfully!");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save configuration");
    } finally {
      setSaving(false);
    }
  };

  const addDevice = () => {
    if (!config) return;

    const newDevice: Device = {
      name: `Device ${config.devices.length + 1}`,
      device_id: "",
      schedules: []
    };

    setConfig({
      ...config,
      devices: [...config.devices, newDevice]
    });
    setSelectedDeviceIndex(config.devices.length);
  };

  const removeDevice = (index: number) => {
    if (!config) return;

    const newDevices = config.devices.filter((_, i) => i !== index);
    setConfig({ ...config, devices: newDevices });

    if (selectedDeviceIndex >= newDevices.length) {
      setSelectedDeviceIndex(Math.max(0, newDevices.length - 1));
    }
  };

  const updateDevice = (index: number, updates: Partial<Device>) => {
    if (!config) return;

    const newDevices = [...config.devices];
    newDevices[index] = { ...newDevices[index], ...updates };
    setConfig({ ...config, devices: newDevices });
  };

  const addSchedule = (deviceIndex: number) => {
    if (!config) return;

    const newSchedule: Schedule = {
      cron: "0 * * * *",
      type: viewTypes[0]?.name || "text",
      params: {}
    };

    const device = config.devices[deviceIndex];
    const schedules = device.schedules || [];

    updateDevice(deviceIndex, {
      schedules: [...schedules, newSchedule]
    });

    setSelectedScheduleIndex(schedules.length);
  };

  const removeSchedule = (deviceIndex: number, scheduleIndex: number) => {
    if (!config) return;

    const device = config.devices[deviceIndex];
    const schedules = device.schedules || [];
    const newSchedules = schedules.filter((_, i) => i !== scheduleIndex);

    updateDevice(deviceIndex, { schedules: newSchedules });

    if (selectedScheduleIndex >= newSchedules.length) {
      setSelectedScheduleIndex(Math.max(0, newSchedules.length - 1));
    }
  };

  const updateSchedule = (
    deviceIndex: number,
    scheduleIndex: number,
    updates: Partial<Schedule>
  ) => {
    if (!config) return;

    const device = config.devices[deviceIndex];
    const schedules = [...(device.schedules || [])];
    schedules[scheduleIndex] = { ...schedules[scheduleIndex], ...updates };

    updateDevice(deviceIndex, { schedules });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (error && !config) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Card className="w-96">
          <CardHeader>
            <CardTitle>Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-red-500">{error}</p>
            <Button onClick={loadData} className="mt-4 w-full">
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const currentDevice = config?.devices[selectedDeviceIndex];
  const currentSchedule = currentDevice?.schedules?.[selectedScheduleIndex];
  const currentViewType = viewTypes.find((vt) => vt.name === currentSchedule?.type);

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Dotmate Configuration</h1>
          <p className="text-muted-foreground">
            Manage your devices and schedules
          </p>
        </div>
        <Button onClick={saveConfig} disabled={saving} size="lg">
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          <Save className="mr-2 h-4 w-4" />
          Save Configuration
        </Button>
      </div>

      {error && (
        <div className="p-4 text-sm text-red-500 bg-red-50 dark:bg-red-900/10 rounded-md">
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>API Configuration</CardTitle>
          <CardDescription>Your Quote/0 API key</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="api-key">API Key</Label>
            <Input
              id="api-key"
              type="password"
              value={config?.api_key || ""}
              onChange={(e) =>
                setConfig({ ...config!, api_key: e.target.value })
              }
              placeholder="Enter your API key"
            />
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Devices</CardTitle>
                <CardDescription>Manage your Quote/0 devices</CardDescription>
              </div>
              <Button onClick={addDevice} size="sm">
                <Plus className="h-4 w-4 mr-2" />
                Add Device
              </Button>
            </CardHeader>
            <CardContent>
              <Tabs
                value={selectedDeviceIndex.toString()}
                onValueChange={(v) => setSelectedDeviceIndex(parseInt(v))}
              >
                <TabsList>
                  {config?.devices.map((device, index) => (
                    <TabsTrigger key={index} value={index.toString()}>
                      {device.name || `Device ${index + 1}`}
                    </TabsTrigger>
                  ))}
                </TabsList>

                {config?.devices.map((device, deviceIndex) => (
                  <TabsContent key={deviceIndex} value={deviceIndex.toString()}>
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor={`device-name-${deviceIndex}`}>
                            Device Name
                          </Label>
                          <Input
                            id={`device-name-${deviceIndex}`}
                            value={device.name}
                            onChange={(e) =>
                              updateDevice(deviceIndex, { name: e.target.value })
                            }
                            placeholder="My Device"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor={`device-id-${deviceIndex}`}>
                            Device ID
                          </Label>
                          <Input
                            id={`device-id-${deviceIndex}`}
                            value={device.device_id}
                            onChange={(e) =>
                              updateDevice(deviceIndex, {
                                device_id: e.target.value,
                              })
                            }
                            placeholder="device-uuid"
                          />
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-4 border-t">
                        <h3 className="font-semibold">Schedules</h3>
                        <div className="space-x-2">
                          <Button
                            onClick={() => addSchedule(deviceIndex)}
                            size="sm"
                            variant="outline"
                          >
                            <Plus className="h-4 w-4 mr-2" />
                            Add Schedule
                          </Button>
                          {config.devices.length > 1 && (
                            <Button
                              onClick={() => removeDevice(deviceIndex)}
                              size="sm"
                              variant="destructive"
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete Device
                            </Button>
                          )}
                        </div>
                      </div>

                      {device.schedules && device.schedules.length > 0 ? (
                        <Tabs
                          value={selectedScheduleIndex.toString()}
                          onValueChange={(v) =>
                            setSelectedScheduleIndex(parseInt(v))
                          }
                        >
                          <TabsList>
                            {device.schedules.map((schedule, index) => (
                              <TabsTrigger key={index} value={index.toString()}>
                                {schedule.type} ({schedule.cron || "manual"})
                              </TabsTrigger>
                            ))}
                          </TabsList>

                          {device.schedules.map((schedule, scheduleIndex) => (
                            <TabsContent
                              key={scheduleIndex}
                              value={scheduleIndex.toString()}
                            >
                              <div className="space-y-4 border rounded-md p-4">
                                <div className="grid grid-cols-2 gap-4">
                                  <div className="space-y-2">
                                    <Label>View Type</Label>
                                    <Select
                                      value={schedule.type}
                                      onValueChange={(value) =>
                                        updateSchedule(
                                          deviceIndex,
                                          scheduleIndex,
                                          { type: value, params: {} }
                                        )
                                      }
                                    >
                                      <SelectTrigger>
                                        <SelectValue />
                                      </SelectTrigger>
                                      <SelectContent>
                                        {viewTypes.map((vt) => (
                                          <SelectItem key={vt.name} value={vt.name}>
                                            {vt.name}
                                          </SelectItem>
                                        ))}
                                      </SelectContent>
                                    </Select>
                                  </div>
                                  <div className="space-y-2">
                                    <Label>Cron Expression</Label>
                                    <Input
                                      value={schedule.cron || ""}
                                      onChange={(e) =>
                                        updateSchedule(
                                          deviceIndex,
                                          scheduleIndex,
                                          { cron: e.target.value }
                                        )
                                      }
                                      placeholder="0 * * * * (every hour)"
                                    />
                                  </div>
                                </div>

                                <div>
                                  <h4 className="font-semibold mb-3">Parameters</h4>
                                  <ViewParamsForm
                                    schema={
                                      viewTypes.find(
                                        (vt) => vt.name === schedule.type
                                      )?.params_schema
                                    }
                                    params={schedule.params || {}}
                                    onChange={(params) =>
                                      updateSchedule(
                                        deviceIndex,
                                        scheduleIndex,
                                        { params }
                                      )
                                    }
                                  />
                                </div>

                                <div className="flex justify-end pt-4 border-t">
                                  <Button
                                    onClick={() =>
                                      removeSchedule(deviceIndex, scheduleIndex)
                                    }
                                    variant="destructive"
                                    size="sm"
                                  >
                                    <Trash2 className="h-4 w-4 mr-2" />
                                    Delete Schedule
                                  </Button>
                                </div>
                              </div>
                            </TabsContent>
                          ))}
                        </Tabs>
                      ) : (
                        <div className="text-center text-sm text-muted-foreground p-8 border-2 border-dashed rounded-md">
                          No schedules configured. Click "Add Schedule" to create
                          one.
                        </div>
                      )}
                    </div>
                  </TabsContent>
                ))}
              </Tabs>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-1">
          {currentSchedule && (
            <PreviewPanel
              viewType={currentSchedule.type}
              params={currentSchedule.params || {}}
            />
          )}
        </div>
      </div>
    </div>
  );
}
