import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Switch } from "@/components/ui/switch";

describe("Switch", () => {
  it("uses the Radix state attributes for visible checked and unchecked styles", async () => {
    const user = userEvent.setup();
    render(<Switch aria-label="Test switch" />);

    const control = screen.getByRole("switch", { name: "Test switch" });
    const thumb = control.querySelector('[data-slot="switch-thumb"]');
    expect(control).toHaveAttribute("data-state", "unchecked");
    expect(control).toHaveClass("data-[state=unchecked]:bg-input");
    expect(thumb).toHaveClass("data-[state=unchecked]:translate-x-0");

    await user.click(control);

    expect(control).toHaveAttribute("data-state", "checked");
    expect(control).toHaveClass("data-[state=checked]:bg-primary");
    expect(thumb).toHaveClass("data-[state=checked]:translate-x-[calc(100%-2px)]");
  });
});
