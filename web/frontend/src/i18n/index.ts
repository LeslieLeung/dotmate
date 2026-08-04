import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import { enUS, zhCN } from "@/i18n/resources";

export type SupportedLanguage = "en-US" | "zh-CN";
export type LanguagePreference = "system" | SupportedLanguage;

export const LANGUAGE_STORAGE_KEY = "dotmate.language";

export function resolveSystemLanguage(
  languages: readonly string[] = typeof navigator === "undefined"
    ? []
    : navigator.languages.length
      ? navigator.languages
      : [navigator.language]
): SupportedLanguage {
  return languages[0]?.toLowerCase().startsWith("zh") ? "zh-CN" : "en-US";
}

export function readLanguagePreference(): LanguagePreference {
  if (typeof localStorage === "undefined") return "system";
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return stored === "zh-CN" || stored === "en-US" || stored === "system"
      ? stored
      : "system";
  } catch {
    return "system";
  }
}

export function resolveLanguagePreference(
  preference: LanguagePreference
): SupportedLanguage {
  return preference === "system" ? resolveSystemLanguage() : preference;
}

function syncDocument(language: string) {
  if (typeof document === "undefined") return;
  document.documentElement.lang = language;
  document.title = i18n.t("app.title");
}

void i18n.use(initReactI18next).init({
  resources: {
    "en-US": { translation: enUS },
    "zh-CN": { translation: zhCN },
  },
  lng: resolveLanguagePreference(readLanguagePreference()),
  fallbackLng: "en-US",
  supportedLngs: ["en-US", "zh-CN"],
  initAsync: false,
  interpolation: { escapeValue: false },
});

i18n.on("languageChanged", syncDocument);
syncDocument(i18n.resolvedLanguage ?? "en-US");

if (typeof window !== "undefined") {
  window.addEventListener("languagechange", () => {
    if (readLanguagePreference() === "system") {
      void i18n.changeLanguage(resolveSystemLanguage());
    }
  });
}

export async function setLanguagePreference(
  preference: LanguagePreference
): Promise<void> {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, preference);
  } catch {
    // Language switching still works when browser storage is unavailable.
  }
  await i18n.changeLanguage(resolveLanguagePreference(preference));
}

export default i18n;
