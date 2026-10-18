import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { HrRequest, TeamMember } from "../api/types";
import { EmptyState } from "../components/Illustration";
import RequestList from "../components/RequestList";
import { fmtDate } from "../i18n";

/** На месте / в отпуске до … / отпуск скоро / уволен; у руководителя — кто И.О. */
function MemberStatus({ m }: { m: TeamMember }) {
  const { t } = useTranslation();
  const a = m.absence;
  let label = <span className="status status-ok">{t("team.working")}</span>;
  if (a?.state === "vacation") label = <span className="status status-warn">{t("team.on_vacation", { date: fmtDate(a.date_to) })}</span>;
  if (a?.state === "planned")
    label = (
      <span className="status status-info">
        {t("team.planned", { from: fmtDate(a.date_from), to: fmtDate(a.date_to) })}
      </span>
    );
  if (a?.state === "dismissed") label = <span className="status status-bad">{t("team.dismissed", { date: fmtDate(a.date_from) })}</span>;
  return (
    <span className="member-status">
      {label}
      {m.deputy && (
        <span className="muted small" title={`${fmtDate(m.deputy.date_from)} – ${fmtDate(m.deputy.date_to)}`}>
          {t("team.deputy", { name: m.deputy.full_name })}
        </span>
      )}
    </span>
  );
}

export default function TeamPage() {
  const { t } = useTranslation();
  const team = useQuery({ queryKey: ["team"], queryFn: () => api<TeamMember[]>("/team") });
  const requests = useQuery({
    queryKey: ["requests", "team"],
    queryFn: () => api<HrRequest[]>("/requests?scope=team"),
  });

  return (
    <div className="stack">
      <h1>{t("team.title")}</h1>
      <section className="card">
        {team.isLoading && <p className="muted">{t("common.loading")}</p>}
        {team.data?.length === 0 && <EmptyState name="team" text={t("team.empty")} />}
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>{t("requests.employee")}</th>
                <th>{t("profile.position")}</th>
                <th>{t("team.status")}</th>
                <th>{t("team.available")}</th>
                <th>{t("team.active")}</th>
              </tr>
            </thead>
            <tbody>
              {team.data?.map((m) => (
                <tr key={m.id}>
                  <td>
                    <Link to={`/team/${m.id}`}>{m.full_name}</Link>
                  </td>
                  <td>{m.position}</td>
                  <td>
                    <MemberStatus m={m} />
                  </td>
                  <td>{t("common.days", { count: m.vacation_days_available })}</td>
                  <td>{m.active_requests}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="card">
        <h2>{t("team.requests")}</h2>
        {requests.data && <RequestList items={requests.data} showEmployee empty={t("requests.empty")} />}
      </section>
    </div>
  );
}
