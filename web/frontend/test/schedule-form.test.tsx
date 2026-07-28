import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScheduleForm } from "@/components/ScheduleForm";
import { getDefaultParams } from "@/lib/schedule-form";
import type { ScheduleTypeDefinition } from "@/lib/api";

const definition: ScheduleTypeDefinition = {
  label: "Example",
  description: "Example schedule",
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
    token: {
      type: "string",
      label: "API Token",
      required: true,
      input: "password",
      section: "main",
      sensitive: true,
      hidden: false,
    },
    border: {
      type: "integer",
      label: "Border",
      required: false,
      input: "select",
      section: "display",
      sensitive: false,
      hidden: false,
      default: 0,
      options: [
        { value: 0, label: "White" },
        { value: 1, label: "Black" },
      ],
    },
    styles: {
      type: "object",
      label: "Styles",
      required: false,
      input: "text",
      section: "advanced",
      sensitive: false,
      hidden: true,
    },
  },
};

describe("ScheduleForm", () => {
  it("initializes typed defaults", () => {
    const defaults = getDefaultParams(definition);
    expect(defaults).toEqual({ border: 0 });
    expect(typeof defaults.border).toBe("number");
  });

  it("omits null defaults and renders null values as empty controls", () => {
    const nullableDefinition: ScheduleTypeDefinition = {
      ...definition,
      fields: {
        ...definition.fields,
        message: { ...definition.fields.message, default: null },
      },
    };

    expect(getDefaultParams(nullableDefinition)).toEqual({ border: 0 });

    render(
      <ScheduleForm
        definition={nullableDefinition}
        values={{ message: null, token: null, border: 0 }}
        errors={{}}
        onChange={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Message*")).toHaveValue("");
    expect(screen.getByLabelText("API Token*")).toHaveValue("");
  });

  it("renders appropriate controls and inline errors without hidden fields", () => {
    render(
      <ScheduleForm
        definition={definition}
        values={{ message: "Hello", token: "secret", border: 0 }}
        errors={{ message: "Message is required" }}
        onChange={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Message*")).toHaveProperty("tagName", "TEXTAREA");
    expect(screen.getByLabelText("API Token*")).toHaveAttribute("type", "password");
    expect(screen.getByText("Message is required")).toBeInTheDocument();
    expect(screen.queryByLabelText("Styles")).not.toBeInTheDocument();
  });
});
