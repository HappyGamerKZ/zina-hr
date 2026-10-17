// Вакансии (HR): цифры по статусам, список с поиском и фильтром, создание и смена статуса.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

import { api } from "../api/client";
import type { EmploymentType, Interviewer, VacancyInput, VacancyStatus, VacancyWithCounts } from "../api/types";
import Icon from "../components/Icon";
import { EmptyState } from "../components/Illustration";
import { icons } from "../components/icons";
import Modal from "../components/Modal";
import { VacancyStatusBadge, useVacancyTitle } from "../components/recruitment";
import { fmtMoney } from "../i18n";

const STATUSES: VacancyStatus[] = ["active", "closed", "draft"];
const EMPLOYMENT: EmploymentType[] = ["full_time", "part_time", "contract", "internship"];

function useInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["recruitment"] });
    qc.invalidateQueries({ queryKey: ["careers"] });
  };
}

function salaryRange(v: VacancyWithCounts, t: TFunction) {
  if (v.salary_from === null && v.salary_to === null) return t("vac.salary_any");
  if (v.salary_from !== null && v.salary_to !== null) return `${fmtMoney(v.salary_from)} – ${fmtMoney(v.salary_to)}`;
  return v.salary_from !== null
    ? t("vac.salary_from_only", { value: fmtMoney(v.salary_from) })
    : t("vac.salary_to_only", { value: fmtMoney(v.salary_to!) });
}

function VacancyForm({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const invalidate = useInvalidate();
  const departments = useQuery({
    queryKey: ["recruitment", "departments"],
    queryFn: () => api<{ id: number; name: string }[]>("/recruitment/departments"),
  });
  const people = useQuery({
    queryKey: ["recruitment", "interviewers"],
    queryFn: () => api<Interviewer[]>("/recruitment/interviewers"),
  });
  const create = useMutation({
    mutationFn: (body: VacancyInput) => api<VacancyWithCounts>("/recruitment/vacancies", { method: "POST", body }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
  });

  const submit = (e: FormEvent<HTMLFormElement>, status: VacancyStatus) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const num = (key: string) => (f.get(key) ? Number(f.get(key)) : null);
    create.mutate({
      title_ru: String(f.get("title_ru")).trim(),
      title_kk: String(f.get("title_kk") ?? "").trim(),
      department_id: num("department_id"),
      hiring_manager_id: num("hiring_manager_id"),
      employment_type: f.get("employment_type") as EmploymentType,
      description: String(f.get("description") ?? ""),
      salary_from: num("salary_from"),
      salary_to: num("salary_to"),
      status,
    });
  };

  // «Сохранить черновик» — та же форма, но статус draft
  const [status, setStatus] = useState<VacancyStatus>("active");

  return (
    <Modal title={t("vac.new_title")} onClose={onClose}>
      <form className="form" onSubmit={(e) => submit(e, status)}>
        <label>
          {t("vac.f_title")} *
          <input name="title_ru" required maxLength={200} autoFocus />
        </label>
        <label>
          {t("vac.f_title_kk")}
          <input name="title_kk" maxLength={200} />
        </label>
        <div className="row-2">
          <label>
            {t("vac.f_department")}
            <select name="department_id" defaultValue="">
              <option value="">{t("vac.not_selected")}</option>
              {departments.data?.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t("vac.f_employment")}
            <select name="employment_type" defaultValue="full_time">
              {EMPLOYMENT.map((k) => (
                <option key={k} value={k}>
                  {t(`vac.employment.${k}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label>
          {t("vac.f_manager")}
          <select name="hiring_manager_id" defaultValue="">
            <option value="">{t("vac.not_selected")}</option>
            {people.data
              ?.filter((p) => p.employee_id !== null)
              .map((p) => (
                <option key={p.id} value={p.employee_id!}>
                  {p.full_name}
                </option>
              ))}
          </select>
        </label>
        <div className="row-2">
          <label>
            {t("vac.f_salary_from")}
            <input name="salary_from" type="number" min={0} step={1000} />
          </label>
          <label>
            {t("vac.f_salary_to")}
            <input name="salary_to" type="number" min={0} step={1000} />
          </label>
        </div>
        <label>
          {t("vac.f_description")}
          <textarea name="description" rows={4} />
        </label>
        {create.error && <p className="error">{create.error.message}</p>}
        <div className="row modal-actions">
          <button type="button" className="btn-ghost" onClick={onClose}>
            {t("vac.cancel")}
          </button>
          <button type="submit" className="btn-secondary" disabled={create.isPending} onClick={() => setStatus("draft")}>
            {t("vac.save_draft")}
          </button>
          <button type="submit" className="btn-primary" disabled={create.isPending} onClick={() => setStatus("active")}>
            {t("vac.publish")}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function StatusActions({ v }: { v: VacancyWithCounts }) {
  const { t } = useTranslation();
  const invalidate = useInvalidate();
  const change = useMutation({
    mutationFn: (status: VacancyStatus) =>
      api<VacancyWithCounts>(`/recruitment/vacancies/${v.id}`, { method: "PATCH", body: { status } }),
    onSuccess: invalidate,
  });
  const next: { status: VacancyStatus; label: string }[] =
    v.status === "active"
      ? [{ status: "closed", label: t("vac.close") }]
      : v.status === "closed"
        ? [{ status: "active", label: t("vac.open") }]
        : [{ status: "active", label: t("vac.publish") }];
  return (
    <div className="row">
      {next.map((n) => (
        <button key={n.status} className="btn-ghost btn-small" disabled={change.isPending} onClick={() => change.mutate(n.status)}>
          {n.label}
        </button>
      ))}
    </div>
  );
}

export default function VacanciesPage() {
  const { t } = useTranslation();
  const title = useVacancyTitle();
  const [creating, setCreating] = useState(false);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<VacancyStatus | "">("");

  const all = useQuery({
    queryKey: ["recruitment", "vacancies"],
    queryFn: () => api<VacancyWithCounts[]>("/recruitment/vacancies"),
  });
  const list = (all.data ?? []).filter(
    (v) =>
      (!status || v.status === status) &&
      (!q || `${v.title_ru} ${v.title_kk}`.toLowerCase().includes(q.trim().toLowerCase())),
  );
  const count = (s: VacancyStatus) => all.data?.filter((v) => v.status === s).length ?? 0;

  return (
    <div className="stack">
      <div className="section-head">
        <div>
          <h1>{t("vac.title")}</h1>
          <p className="muted page-sub">{t("vac.subtitle")}</p>
        </div>
        <button className="btn-primary" onClick={() => setCreating(true)}>
          <Icon src={icons.add} size={18} />
          {t("vac.create")}
        </button>
      </div>

      <div className="stat-grid">
        <button className="stat-card tone-1" onClick={() => setStatus("")}>
          <span className="stat-label">{t("vac.total")}</span>
          <strong>{all.data?.length ?? "—"}</strong>
        </button>
        {STATUSES.map((s, idx) => (
          <button key={s} className={`stat-card tone-${idx + 2}${status === s ? " selected" : ""}`} onClick={() => setStatus(s)}>
            <span className="stat-label">{t(`vac.stat.${s}`)}</span>
            <strong>{all.data ? count(s) : "—"}</strong>
          </button>
        ))}
      </div>

      <section className="card">
        <div className="section-head">
          <h2>{t("vac.all")}</h2>
          <span className="status status-neutral">{t("vac.count", { count: list.length })}</span>
        </div>
        <div className="filters">
          <label className="search-field">
            <Icon src={icons.search} size={18} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("vac.search")} aria-label={t("vac.search")} />
          </label>
          <select value={status} onChange={(e) => setStatus(e.target.value as VacancyStatus | "")} aria-label={t("vac.all_statuses")}>
            <option value="">{t("vac.all_statuses")}</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`vac.status.${s}`)}
              </option>
            ))}
          </select>
        </div>

        {all.isLoading && <p className="muted">{t("common.loading")}</p>}
        {all.data && list.length === 0 && <EmptyState name="folder" text={t("vac.empty")} />}
        <ul className="vacancy-list">
          {list.map((v) => (
            <li key={v.id} className="vacancy-row">
              <div className="vacancy-main">
                <strong>{title(v)}</strong>
                <span className="muted small">
                  {[v.department?.name, t(`vac.employment.${v.employment_type}`), salaryRange(v, t)]
                    .filter(Boolean)
                    .join(" · ")}
                </span>
              </div>
              <Link to={`/recruitment?vacancy=${v.id}`} className="vacancy-count small">
                <Icon src={icons.candidates} size={16} />
                {t("vac.candidates", { count: v.candidates_count })}
                {v.active_candidates_count > 0 && <span className="muted"> · {t("vac.in_work", { count: v.active_candidates_count })}</span>}
              </Link>
              <VacancyStatusBadge status={v.status} />
              <StatusActions v={v} />
            </li>
          ))}
        </ul>
      </section>

      {creating && <VacancyForm onClose={() => setCreating(false)} />}
    </div>
  );
}
