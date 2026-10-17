// Публичная форма резюме на странице входа (без авторизации). Временный UI — дизайн сделает фронтенд.
import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { PublicVacancy } from "../api/types";

function firstError(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const d = data as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  const first = Object.values(d)[0];
  return Array.isArray(first) ? String(first[0]) : typeof first === "string" ? first : null;
}

export default function ResumeForm() {
  const { t, i18n } = useTranslation();
  const vacancies = useQuery({
    queryKey: ["careers", "vacancies"],
    queryFn: () => api<PublicVacancy[]>("/careers/vacancies"),
  });
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const pdf = data.get("resume_pdf") as File | null;
    if (pdf && pdf.size === 0) data.delete("resume_pdf"); // файл не выбран
    if (!data.get("profile_url") && !data.get("resume_pdf")) {
      setError(t("careers.resume_hint"));
      return;
    }
    if (!data.get("expected_salary")) data.delete("expected_salary");
    data.set("consent", data.get("consent") ? "true" : "false");
    setBusy(true);
    setError(null);
    try {
      // multipart: файл и поля одним запросом; вход и CSRF не нужны (публичный адрес)
      const res = await fetch("/api/v1/careers/applications", { method: "POST", body: data });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(res.status === 429 ? "Слишком много отправок, попробуйте позже" : firstError(body) ?? `HTTP ${res.status}`);
      }
      form.reset();
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  if (sent)
    return (
      <div className="stack">
        <h1>✅ {t("careers.sent_title")}</h1>
        <p className="muted">{t("careers.sent_text")}</p>
        <button type="button" className="btn-ghost" onClick={() => setSent(false)}>
          {t("careers.again")}
        </button>
      </div>
    );

  return (
    <form className="form" onSubmit={onSubmit}>
      <div>
        <h1>{t("careers.title")}</h1>
        <p className="muted">{t("careers.subtitle")}</p>
      </div>
      <label>
        {t("careers.full_name")} *
        <input name="full_name" required maxLength={200} autoComplete="name" />
      </label>
      <div className="row-2">
        <label>
          {t("careers.email")} *
          <input name="email" type="email" required autoComplete="email" />
        </label>
        <label>
          {t("careers.phone")} *
          <input name="phone" type="tel" required placeholder="+7 701 123 45 67" autoComplete="tel" />
        </label>
      </div>
      <label>
        {t("careers.social")}
        <input name="social" placeholder="@username" />
      </label>
      <label>
        {t("careers.position")} *
        <select name="vacancy_id" required defaultValue="">
          <option value="" disabled>
            {t("careers.choose")}
          </option>
          {vacancies.data?.map((v) => (
            <option key={v.id} value={v.id}>
              {i18n.language === "kk" && v.title_kk ? v.title_kk : v.title_ru}
              {v.department && ` · ${v.department}`}
            </option>
          ))}
        </select>
      </label>
      <label>
        {t("careers.profile_url")}
        <input name="profile_url" type="url" placeholder="https://hh.kz/resume/..." />
      </label>
      <label>
        {t("careers.resume_pdf")}
        <input name="resume_pdf" type="file" accept="application/pdf,.pdf" />
      </label>
      <label>
        {t("careers.salary")}
        <input name="expected_salary" type="number" min={0} step={1} />
      </label>
      <label>
        {t("careers.comment")}
        <textarea name="comment" rows={3} maxLength={2000} />
      </label>
      {/* ловушка для ботов: человек это поле не видит и не заполняет */}
      <input name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" style={{ display: "none" }} />
      <label className="choice">
        <input name="consent" type="checkbox" required />
        {t("careers.consent")} *
      </label>
      {error && <p className="error">{error}</p>}
      <button className="btn-primary" disabled={busy}>
        {t("careers.submit")}
      </button>
    </form>
  );
}
