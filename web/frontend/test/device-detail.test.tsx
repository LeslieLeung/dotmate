import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getDevice, getScheduleTypes } = vi.hoisted(() => ({
  getDevice: vi.fn(),
  getScheduleTypes: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    devicesApi: { ...actual.devicesApi, get: getDevice },
    schemaApi: { getScheduleTypes },
  };
});

import { DeviceDetailPage } from "@/pages/DeviceDetailPage";
import { TooltipProvider } from "@/components/ui/tooltip";

function makeDevice() {
  return {
    id: 1,
    name: "Desk",
    device_id: "device-1",
    api_credential_id: 1,
    api_credential_name: "Personal",
    vendor: "mindreset",
    vendor_capabilities: [],
    show_battery_icon: false,
    show_battery_percentage: false,
    show_refresh_time: false,
    schedules: [
      {
        id: 4,
        name: "Coding status",
        cron: "*/5 * * * *",
        type: "code_status",
        type_label: "WakaTime Coding Status",
        params: {
          wakatime_user_id: "leslie",
          wakatime_api_key: "never-render-this-secret",
        },
        summary: [{ label: "WakaTime User ID", value: "leslie" }],
      },
    ],
  };
}

describe("DeviceDetailPage", () => {
  afterEach(cleanup);

  beforeEach(() => {
    getDevice.mockResolvedValue(makeDevice());
    getScheduleTypes.mockResolvedValue({
      code_status: {
        label: "WakaTime Coding Status",
        description: "Coding status",
        fields: {},
      },
    });
  });

  it("renders only the server-provided safe summary", async () => {
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/devices/1"]}>
          <Routes>
            <Route path="/devices/:id" element={<DeviceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    );

    expect((await screen.findAllByText("Coding status")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("WakaTime Coding Status").length).toBeGreaterThan(0);
    expect(screen.getAllByText("leslie").length).toBeGreaterThan(0);
    expect(screen.queryByText("never-render-this-secret")).not.toBeInTheDocument();
  });

  it("renders cached device status and its per-device polling policy", async () => {
    const user = userEvent.setup();
    getDevice.mockResolvedValue({
      ...makeDevice(),
      vendor_capabilities: ["status"],
      remote_status: {
        remote_device_id: "device-1",
        alias: "Desk",
        location: "Office",
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
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/devices/1"]}>
          <Routes>
            <Route path="/devices/:id" element={<DeviceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    );

    expect(await screen.findByText("Charging")).toBeInTheDocument();
    expect(screen.getByText("-62 dBm")).toBeInTheDocument();
    expect(screen.getByText("1.2.3")).toBeInTheDocument();
    expect(screen.getByText("Follow device · 5 min (power)")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Refresh interval" }));
    expect(screen.getByRole("dialog", { name: "Status refresh interval" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Mode" })).toHaveTextContent("Follow device");
  });

  it("closes an untouched create form without a discard confirmation", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/devices/1"]}>
          <Routes>
            <Route path="/devices/:id" element={<DeviceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    );

    await screen.findByRole("heading", { name: "Desk" });
    await user.click(screen.getByRole("button", { name: "Add Schedule" }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Add Schedule" })).not.toBeInTheDocument();
    });
  });

  it("does not confirm a type change when the current parameters only contain defaults", async () => {
    const user = userEvent.setup();
    getDevice.mockResolvedValue({
      ...makeDevice(),
      schedules: [],
    });
    getScheduleTypes.mockResolvedValue({
      text: {
        label: "Text Message",
        description: "Send a custom message.",
        fields: {
          message: {
            type: "string",
            label: "Message",
            required: true,
            input: "textarea",
            section: "main",
            sensitive: false,
            hidden: false,
          },
          title: {
            type: "string",
            label: "Title",
            required: false,
            input: "text",
            section: "main",
            sensitive: false,
            hidden: false,
            default: null,
          },
        },
      },
      code_status: {
        label: "WakaTime Coding Status",
        description: "Coding status.",
        fields: {},
      },
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/devices/1"]}>
          <Routes>
            <Route path="/devices/:id" element={<DeviceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    );

    await screen.findByRole("heading", { name: "Desk" });
    const addButtons = screen.getAllByRole("button", { name: "Add Schedule" });
    expect(addButtons).toHaveLength(2);
    await user.click(addButtons[0]);
    await user.click(screen.getByRole("combobox", { name: "Schedule Type*" }));
    await user.click(screen.getByRole("option", { name: "Text Message" }));
    await user.click(screen.getByRole("combobox", { name: "Schedule Type*" }));
    await user.click(screen.getByRole("option", { name: "WakaTime Coding Status" }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Schedule Type*" })).toHaveTextContent(
      "WakaTime Coding Status"
    );
  });

  it("does not confirm after an edit is reverted to its initial value", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/devices/1"]}>
          <Routes>
            <Route path="/devices/:id" element={<DeviceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    );

    await screen.findByRole("heading", { name: "Desk" });
    const editButtons = screen.getAllByRole("button", { name: "Edit Coding status" });
    expect(editButtons).toHaveLength(2);
    await user.click(editButtons[0]);
    const nameInput = screen.getByLabelText("Name*");
    await user.clear(nameInput);
    await user.type(nameInput, "Coding status");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Edit Schedule" })).not.toBeInTheDocument();
    });
  });

  it("closes the discard confirmation when keeping an edited form", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/devices/1"]}>
          <Routes>
            <Route path="/devices/:id" element={<DeviceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    );

    await screen.findByRole("heading", { name: "Desk" });
    const editButtons = screen.getAllByRole("button", { name: "Edit Coding status" });
    expect(editButtons).toHaveLength(2);
    await user.click(editButtons[0]);
    await user.type(screen.getByLabelText("Name*"), " updated");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Keep Editing" }));

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    });
    expect(screen.getByLabelText("Name*")).toHaveValue("Coding status updated");
  });

  it("closes both the confirmation and form when discarding an edited form", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/devices/1"]}>
          <Routes>
            <Route path="/devices/:id" element={<DeviceDetailPage />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    );

    await screen.findByRole("heading", { name: "Desk" });
    const editButtons = screen.getAllByRole("button", { name: "Edit Coding status" });
    expect(editButtons).toHaveLength(2);
    await user.click(editButtons[0]);
    await user.type(screen.getByLabelText("Name*"), " updated");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Discard Changes" }));

    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
      expect(screen.queryByRole("dialog", { name: "Edit Schedule" })).not.toBeInTheDocument();
    });
  });
});
