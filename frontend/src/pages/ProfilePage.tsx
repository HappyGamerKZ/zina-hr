import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Profile } from "../api/types";
import ProfileCard from "../components/ProfileCard";

export default function ProfilePage() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ["profile"],
    queryFn: () => api<Profile>("/me/profile"),
  });
  if (isLoading) return <p className="muted">{t("common.loading")}</p>;
  if (error || !data) return <p className="error">{t("common.error")}</p>;
  return <ProfileCard profile={data} />;
}
