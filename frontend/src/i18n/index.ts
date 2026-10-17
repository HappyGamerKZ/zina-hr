import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import kk from "./kk";
import ru from "./ru";
import type { Lang } from "../api/types";

function savedLang(): Lang {
  try {
    return localStorage.getItem("lang") === "kk" ? "kk" : "ru";
  } catch {
    return "ru";
  }
}

i18n.use(initReactI18next).init({
  resources: { ru: { translation: ru }, kk: { translation: kk } },
  lng: savedLang(),
  fallbackLng: "ru",
  interpolation: { escapeValue: false },
});

export function setLang(lang: Lang) {
  try {
    localStorage.setItem("lang", lang);
  } catch {
    /* приватный режим — язык просто не запомнится */
  }
  i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
}

const LOCALES: Record<Lang, string> = { ru: "ru-RU", kk: "kk-KZ" };

export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(LOCALES[i18n.language as Lang] ?? "ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function fmtDateTime(value: string): string {
  return new Date(value).toLocaleString(LOCALES[i18n.language as Lang] ?? "ru-RU", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtMoney(value: string | number): string {
  return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₸`;
}

export default i18n;
