import { useState } from "react";
import { Languages } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Field,
  FieldDescription,
  FieldLabel,
} from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  readLanguagePreference,
  setLanguagePreference,
  type LanguagePreference,
} from "@/i18n";

export function LanguageSettingsCard() {
  const { t } = useTranslation();
  const [preference, setPreference] = useState(readLanguagePreference);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Languages />
          {t("language.title")}
        </CardTitle>
        <CardDescription>{t("language.description")}</CardDescription>
      </CardHeader>
      <CardContent>
        <Field>
          <FieldLabel htmlFor="display-language">{t("language.label")}</FieldLabel>
          <Select
            value={preference}
            onValueChange={(value) => {
              const next = value as LanguagePreference;
              setPreference(next);
              void setLanguagePreference(next);
            }}
          >
            <SelectTrigger id="display-language" className="w-full sm:w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="system">{t("language.system")}</SelectItem>
                <SelectItem value="zh-CN">{t("language.zhCN")}</SelectItem>
                <SelectItem value="en-US">{t("language.enUS")}</SelectItem>
              </SelectGroup>
            </SelectContent>
          </Select>
          {preference === "system" && (
            <FieldDescription>{t("language.systemHint")}</FieldDescription>
          )}
        </Field>
      </CardContent>
    </Card>
  );
}
