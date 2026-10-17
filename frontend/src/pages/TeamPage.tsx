import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { HrRequest, TeamMember } from "../api/types";
import { EmptyState } from "../components/Illustration";
import RequestList from "../components/RequestList";

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
