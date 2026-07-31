import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LanguageSettingsCard } from "@/components/LanguageSettingsCard";
import i18n, {
  LANGUAGE_STORAGE_KEY,
  readLanguagePreference,
  resolveLanguagePreference,
  resolveSystemLanguage,
  setLanguagePreference,
} from "@/i18n";
import { enUS, zhCN } from "@/i18n/resources";
import { ApiError, devicesApi } from "@/lib/api";

describe("i18n", () => {
  afterEach(async () => {
    localStorage.clear();
    await i18n.changeLanguage("en-US");
  });

  it("maps Chinese system locales to Simplified Chinese and all others to English", () => {
    expect(resolveSystemLanguage(["zh-Hant-TW"])).toBe("zh-CN");
    expect(resolveSystemLanguage(["zh-CN"])).toBe("zh-CN");
    expect(resolveSystemLanguage(["en-US"])).toBe("en-US");
    expect(resolveSystemLanguage([])).toBe("en-US");
  });

  it("falls back to system mode for missing or invalid stored preferences", () => {
    expect(readLanguagePreference()).toBe("system");
    localStorage.setItem(LANGUAGE_STORAGE_KEY, "fr-FR");
    expect(readLanguagePreference()).toBe("system");
    expect(resolveLanguagePreference("en-US")).toBe("en-US");
  });

  it("keeps the English and Chinese resource keys in sync", () => {
    expect(Object.keys(zhCN).sort()).toEqual(Object.keys(enUS).sort());
  });

  it("switches immediately, persists the preference, and updates document metadata", async () => {
    const user = userEvent.setup();
    render(<LanguageSettingsCard />);

    await user.click(screen.getByRole("combobox", { name: "Display language" }));
    await user.click(screen.getByRole("option", { name: "中文" }));

    expect(readLanguagePreference()).toBe("zh-CN");
    expect(i18n.resolvedLanguage).toBe("zh-CN");
    expect(document.documentElement.lang).toBe("zh-CN");
    expect(document.title).toBe("Dotmate 管理后台");
    expect(screen.getByText("选择此浏览器使用的界面语言。")).toBeInTheDocument();
  });

  it("can return to system mode without storing the resolved language", async () => {
    await setLanguagePreference("zh-CN");
    await setLanguagePreference("system");
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("system");
  });

  it("turns structured API error codes into the active language", async () => {
    await setLanguagePreference("zh-CN");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            message: "Device not found",
            code: "device.notFound",
            params: {},
            fields: {},
            field_errors: {},
          },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } }
      )
    );

    const error = await devicesApi.get(999).catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      message: "未找到设备",
      code: "device.notFound",
    });
    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      headers: expect.objectContaining({
        "X-Dotmate-Structured-Errors": "1",
      }),
    });
    fetchMock.mockRestore();
  });
});
