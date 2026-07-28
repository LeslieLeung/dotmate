import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const { authStatus } = vi.hoisted(() => ({ authStatus: vi.fn() }));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, authApi: { status: authStatus } };
});

import { LoginPage } from "@/pages/LoginPage";

describe("LoginPage", () => {
  it("skips login when the server is in open mode", async () => {
    authStatus.mockResolvedValue({ auth_required: false, authenticated: true });
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Admin Home</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Admin Home")).toBeInTheDocument());
  });
});
