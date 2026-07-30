import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  listKeys: vi.fn(),
  createBatch: vi.fn(),
  listVendors: vi.fn(),
  listDevices: vi.fn(),
  listDeviceModels: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    settingsApi: { get: mocks.getSettings, update: mocks.updateSettings },
    apiKeysApi: {
      ...actual.apiKeysApi,
      list: mocks.listKeys,
      createBatch: mocks.createBatch,
    },
    vendorsApi: { list: mocks.listVendors },
    deviceModelsApi: { list: mocks.listDeviceModels },
    devicesApi: { ...actual.devicesApi, list: mocks.listDevices },
  };
});

import { DevicesPage } from "@/pages/DevicesPage";
import { SettingsPage } from "@/pages/SettingsPage";

const vendor = {
  id: "mindreset",
  label: "MindReset",
  description: "MindReset Open API",
  capabilities: ["devices"],
  credential_hint: "Paste your MindReset key",
  supports_credential_validation: true,
  supports_device_discovery: true,
};

const quote0Model = {
  id: "quote0",
  vendor_id: "mindreset",
  label: "Quote/0",
  description: "MindReset Quote/0",
  width: 296,
  height: 152,
  supports_text: true,
  supports_image: true,
  supports_battery_overlay: true,
  supports_page_id: false,
  device_id_label: "Device ID",
  device_id_example: "device-xxxxxxxx",
  display_capabilities: ["text", "image", "battery_overlay", "refresh_time_overlay"],
};

const credential = {
  id: 1,
  name: "Personal",
  vendor: "mindreset",
  vendor_label: "MindReset",
  masked_key: "abcd••••wxyz",
  device_count: 1,
  validation_status: "validated" as const,
};

function makeDevice(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    name: "Desk",
    device_id: "desk-1",
    vendor: "mindreset",
    vendor_label: "MindReset",
    vendor_capabilities: ["devices"],
    device_model: "quote0",
    device_model_label: "Quote/0",
    display_width: 296,
    display_height: 152,
    display_capabilities: ["text", "image", "battery_overlay", "refresh_time_overlay"],
    api_credential_id: 1,
    api_credential_name: "Personal",
    show_battery_icon: false,
    show_battery_percentage: false,
    show_refresh_time: false,
    remote_status: null,
    status_policy: {
      refresh_interval_minutes: null,
      effective_interval_minutes: null,
      interval_source: null,
      state: "pending",
      last_attempt_at: null,
      last_success_at: null,
      next_refresh_at: null,
      last_error: null,
      refresh_requested_at: null,
    },
    schedules: [],
    ...overrides,
  };
}

describe("multi-vendor management", () => {
  beforeEach(() => {
    mocks.getSettings.mockResolvedValue({ request_interval: 1 });
    mocks.listKeys.mockResolvedValue([credential]);
    mocks.listVendors.mockResolvedValue([vendor]);
    mocks.listDeviceModels.mockResolvedValue([quote0Model]);
    mocks.createBatch.mockResolvedValue({
      results: [
        { index: 0, name: "One", vendor: "mindreset", status: "success", sync: { fetched: 0, created: 0, linked: 0, duplicates: 0 } },
        { index: 1, name: "Two", vendor: "mindreset", status: "success", sync: { fetched: 0, created: 0, linked: 0, duplicates: 0 } },
      ],
    });
    mocks.listDevices.mockResolvedValue([]);
  });

  it("submits several API keys in one batch", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    await user.click(await screen.findByRole("button", { name: "Add API Keys" }));
    await user.click(screen.getByRole("button", { name: "Add Another" }));

    const names = screen.getAllByPlaceholderText("e.g. Personal");
    const keys = screen.getAllByPlaceholderText("Enter API key");
    await user.type(names[0], "One");
    await user.type(keys[0], "key-one");
    await user.type(names[1], "Two");
    await user.type(keys[1], "key-two");
    await user.click(screen.getByRole("button", { name: "Add 2 Keys" }));

    await waitFor(() => expect(mocks.createBatch).toHaveBeenCalledWith([
      { name: "One", vendor: "mindreset", api_key: "key-one" },
      { name: "Two", vendor: "mindreset", api_key: "key-two" },
    ]));
  });

  it("filters a multi-device list by API key", async () => {
    mocks.listKeys.mockResolvedValue([
      credential,
      { ...credential, id: 2, name: "Work", masked_key: "work••••key2" },
    ]);
    mocks.listDevices.mockResolvedValue([
      makeDevice(),
      makeDevice({
        id: 2,
        name: "Office",
        device_id: "office-1",
        api_credential_id: 2,
        api_credential_name: "Work",
      }),
    ]);
    render(<MemoryRouter initialEntries={["/devices?api_key_id=2"]}><DevicesPage /></MemoryRouter>);
    expect(await screen.findByText("Office")).toBeInTheDocument();
    expect(screen.queryByText("Desk")).not.toBeInTheDocument();
  });

  it("shows the latest cached status without calling the vendor", async () => {
    mocks.listDevices.mockResolvedValue([
      makeDevice({
        vendor_capabilities: ["devices", "status"],
        remote_status: {
          remote_device_id: "desk-1",
          alias: "Desk",
          location: null,
          version: "1.2.3",
          current: "Power Active",
          description: "Ready",
          battery: "Charging",
          wifi: "-62 dBm",
          last_render: "12/18/2025 14:11",
          rotated: false,
          border: 0,
          image_count: 1,
          next_battery_render: "12/18/2025 17:11",
          next_power_render: "12/18/2025 14:16",
        },
        status_policy: {
          refresh_interval_minutes: null,
          effective_interval_minutes: 5,
          interval_source: "power",
          state: "ready",
          last_attempt_at: "2026-07-21T08:00:00",
          last_success_at: "2026-07-21T08:00:00",
          next_refresh_at: "2026-07-21T08:05:00",
          last_error: null,
          refresh_requested_at: null,
        },
      }),
    ]);

    render(<MemoryRouter><DevicesPage /></MemoryRouter>);

    expect(await screen.findByText("Power Active")).toBeInTheDocument();
    expect(screen.getByText("Charging · -62 dBm")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getAllByText("Quote/0").length).toBeGreaterThan(0);
    expect(screen.getAllByText("296×152").length).toBeGreaterThan(0);
  });
});
