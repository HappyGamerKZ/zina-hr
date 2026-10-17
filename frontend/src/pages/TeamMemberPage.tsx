import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";
import type { Profile } from "../api/types";
import ProfileCard from "../components/ProfileCard";

export default function TeamMemberPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ["team", id],
    queryFn: () => api<Profile>(`/team/${id}`),
    retry: false,
  });

  return (
    <div className="stack narrow">
      <Link to="/team" className="muted">
        ← {t("common.back")}
      </Link>
      {isLoading && <p className="muted">{t("common.loading")}</p>}
      {error instanceof ApiError && error.status === 404 && <p className="error">404</p>}
      {data && <ProfileCard profile={data} />}
    </div>
  );
}
