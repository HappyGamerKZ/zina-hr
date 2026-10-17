// Обзор подбора на главной у HR: цифры дня, лучшие кандидаты, ближайшие интервью.
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import Icon from "./Icon";
import { EmptyState } from "./Illustration";
import { icons } from "./icons";
import { MatchBadge, StageBadge, UpcomingInterviews, useRecruitmentSummary, useVacancyTitle } from "./recruitment";

export default function HrOverview() {
  const { t } = useTranslation();
  const title = useVacancyTitle();
  const { data } = useRecruitmentSummary();
  if (!data || data.open_vacancies === undefined) return null;

  const stats = [
    { key: "open_vacancies", value: data.open_vacancies, to: "/recruitment/vacancies", icon: icons.recruitment },
    { key: "active_candidates", value: data.active_candidates ?? 0, to: "/recruitment", icon: icons.candidates },
    { key: "upcoming", value: data.upcoming_count, to: "/recruitment/calendar", icon: icons.calendar },
    { key: "pending_requests", value: data.pending_requests ?? 0, to: "/team/approvals", icon: icons.approvals },
  ];
  const top = data.top_candidates ?? [];

  return (
    <>
      <div className="stat-grid">
        {stats.map((s, idx) => (
          <Link key={s.key} to={s.to} className={`stat-card tone-${idx + 1}`}>
            <span className="stat-label">
              <Icon src={s.icon} size={18} />
              {t(`hrdash.${s.key}`)}
            </span>
            <strong>{s.value}</strong>
          </Link>
        ))}
      </div>

      <div className="grid-2">
        <section className="card">
          <div className="section-head">
            <h2 className="icon-title">
              <Icon src={icons.performance} />
              {t("hrdash.top")}
            </h2>
            <Link to="/recruitment" className="icon-link">
              {t("recruitment.all_resumes")}
              <Icon src={icons.forward} size={16} />
            </Link>
          </div>
          {top.length === 0 ? (
            <EmptyState name="team" text={t("hrdash.no_top")} />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("hrdash.candidate")}</th>
                    <th className="col-position">{t("hrdash.position")}</th>
                    <th title={t("hrdash.match_hint")}>{t("hrdash.match")}</th>
                    <th>{t("hrdash.stage")}</th>
                  </tr>
                </thead>
                <tbody>
                  {top.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <Link to={`/recruitment/${c.id}`}>{c.full_name}</Link>
                      </td>
                      <td className="muted col-position">{title(c.vacancy)}</td>
                      <td>
                        <MatchBadge score={c.match_score} />
                      </td>
                      <td>
                        <StageBadge stage={c.stage} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="muted small hint-line">{t("hrdash.match_hint")}</p>
        </section>

        <section className="card">
          <h2>{t("recruitment.upcoming")}</h2>
          <UpcomingInterviews items={data.upcoming_interviews.slice(0, 4)} />
          <Link to="/recruitment/calendar" className="btn-secondary block-btn">
            <Icon src={icons.calendar} size={18} />
            {t("hrdash.view_calendar")}
          </Link>
        </section>
      </div>
    </>
  );
}
