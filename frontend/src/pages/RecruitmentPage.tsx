import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { CandidateListItem, CandidateStage, VacancyWithCounts } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/Illustration";
import {
  StageBadge,
  UpcomingInterviews,
  salary,
  useRecruitmentSummary,
  useVacancyTitle,
} from "../components/recruitment";
import { fmtDate, fmtDateTime } from "../i18n";

const STAGES: CandidateStage[] = ["screening", "hr_interview", "tech_interview", "hired", "rejected"];

export default function RecruitmentPage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const hr = can("recruitment.manage");
  const title = useVacancyTitle();
  const [params, setParams] = useSearchParams();
  const vacancy = params.get("vacancy") ?? "";
  const stage = params.get("stage") ?? "";
  const q = params.get("q") ?? "";

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const summary = useRecruitmentSummary();
  const vacancies = useQuery({
    queryKey: ["recruitment", "vacancies"],
    queryFn: () => api<VacancyWithCounts[]>("/recruitment/vacancies"),
    enabled: hr,
  });
  const query = new URLSearchParams({ ...(vacancy && { vacancy }), ...(stage && { stage }), ...(q && { q }) });
  const candidates = useQuery({
    queryKey: ["recruitment", "candidates", vacancy, stage, q],
    queryFn: () => api<CandidateListItem[]>(`/recruitment/candidates?${query}`),
  });

  return (
    <div className="stack">
      <h1>{t("recruitment.title")}</h1>

      <div className="grid-2">
        <section className="card">
          <h2>{t("recruitment.upcoming")}</h2>
          {summary.data && <UpcomingInterviews items={summary.data.upcoming_interviews} />}
        </section>
        {hr && summary.data?.by_stage && (
          <section className="card">
            <h2>{t("recruitment.steps")}</h2>
            <ul className="note-list">
              {STAGES.map((s) => (
                <li key={s}>
                  <a href={`?stage=${s}`} onClick={(e) => { e.preventDefault(); setFilter("stage", s); }}>
                    <span className="row">
                      <StageBadge stage={s} /> <strong>{summary.data?.by_stage?.[s] ?? 0}</strong>
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      <section className="card stack">
        {hr && (
          <div className="row">
            <select value={vacancy} onChange={(e) => setFilter("vacancy", e.target.value)} style={{ maxWidth: 260 }}>
              <option value="">{t("recruitment.all_vacancies")}</option>
              {vacancies.data?.map((v) => (
                <option key={v.id} value={v.id}>
                  {title(v)} ({v.candidates_count})
                </option>
              ))}
            </select>
            <select value={stage} onChange={(e) => setFilter("stage", e.target.value)} style={{ maxWidth: 220 }}>
              <option value="">{t("recruitment.all_stages")}</option>
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {t(`recruitment.stage.${s}`)}
                </option>
              ))}
            </select>
            <input
              defaultValue={q}
              placeholder={t("recruitment.search")}
              onKeyDown={(e) => e.key === "Enter" && setFilter("q", e.currentTarget.value.trim())}
              style={{ maxWidth: 280 }}
            />
          </div>
        )}
        {candidates.isLoading && <p className="muted">{t("common.loading")}</p>}
        {candidates.data?.length === 0 && <EmptyState name="team" text={t("recruitment.empty")} />}
        <ul className="request-list">
          {candidates.data?.map((c) => (
            <li key={c.id}>
              <Link to={`/recruitment/${c.id}`} className="request-row">
                <div className="request-main">
                  <span className="request-type">
                    {c.full_name}
                    {!c.reviewed && c.stage === "screening" && (
                      <span className="status status-warn" style={{ marginLeft: 8 }}>{t("recruitment.new")}</span>
                    )}
                  </span>
                  <span className="muted small">
                    {title(c.vacancy)} · {t("recruitment.salary")}: {salary(c.expected_salary)} ·{" "}
                    {t("recruitment.received")}: {fmtDate(c.created_at)}
                  </span>
                  {c.next_interview && (
                    <span className="small">
                      {t(`recruitment.kind.${c.next_interview.kind}`)}: {fmtDateTime(c.next_interview.scheduled_at)}
                    </span>
                  )}
                </div>
                <StageBadge stage={c.stage} />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
