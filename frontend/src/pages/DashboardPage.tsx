import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Dashboard } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { AssignmentRow } from "../components/academy";
import { RecruitmentWidget } from "../components/recruitment";
import RequestList from "../components/RequestList";
import { fmtDateTime } from "../i18n";

const QUICK_ICONS: Record<string, string> = { vacation: "🏖", advance: "₸", ai: "✦", academy: "▶" };

export default function DashboardPage() {
  const { t } = useTranslation();
  const { can } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/me/dashboard"),
  });

  if (isLoading) return <p className="muted">{t("common.loading")}</p>;
  if (error || !data) return <p className="error">{t("common.error")}</p>;

  const { profile } = data;
  const firstName = profile.full_name.split(" ")[1] ?? profile.full_name;

  return (
    <div className="stack">
      <section className="hero card">
        <div>
          <h1>{t("dashboard.greeting", { name: firstName })}</h1>
          <p className="muted">
            {profile.position} · {profile.department}
          </p>
        </div>
        <div className="hero-stat">
          <span className="muted small">{t("dashboard.vacation_left")}</span>
          <strong>{t("common.days", { count: profile.vacation_balance.days_available })}</strong>
        </div>
      </section>

      {can("requests.approve") && data.approvals_count > 0 && (
        <Link to="/team/approvals" className="card alert">
          {t("dashboard.approvals", { count: data.approvals_count })}
          <span>{t("dashboard.open_approvals")}</span>
        </Link>
      )}

      <section>
        <h2>{t("dashboard.quick")}</h2>
        <div className="quick-grid">
          {data.quick_services.map((q) => (
            <Link key={q.key} to={q.link} className="card quick">
              <span className="quick-icon" aria-hidden>
                {QUICK_ICONS[q.key]}
              </span>
              {t(`dashboard.q_${q.key}`)}
            </Link>
          ))}
        </div>
      </section>

      <div className="grid-2">
        <section className="card">
          <div className="section-head">
            <h2>{t("dashboard.recent")}</h2>
            <Link to="/requests">{t("dashboard.all_requests")}</Link>
          </div>
          <RequestList items={data.recent_requests} empty={t("requests.empty")} />
        </section>

        <div className="stack">
          {can("recruitment.interviews") && <RecruitmentWidget />}
          <section className="card">
            <div className="section-head">
              <h2>{t("dashboard.learning")}</h2>
              <Link to="/academy">→</Link>
            </div>
            {data.courses.length === 0 ? (
              <p className="muted">{t("dashboard.no_courses")}</p>
            ) : (
              data.courses.map((a) => <AssignmentRow key={a.id} a={a} />)
            )}
          </section>

          <section className="card">
            <div className="section-head">
              <h2>{t("dashboard.notifications")}</h2>
              <Link to="/notifications">→</Link>
            </div>
            {data.notifications.length === 0 ? (
              <p className="muted">{t("dashboard.no_notifications")}</p>
            ) : (
              <ul className="note-list">
                {data.notifications.map((n) => (
                  <li key={n.id} className={n.is_read ? "" : "unread"}>
                    <Link to={n.link || "/notifications"}>
                      <strong>{n.title}</strong>
                      <span className="muted small">{fmtDateTime(n.created_at)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
