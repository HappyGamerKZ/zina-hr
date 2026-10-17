import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { HrRequest } from "../api/types";
import RequestList from "../components/RequestList";

export default function ApprovalsPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ["requests", "approvals"],
    queryFn: () => api<HrRequest[]>("/requests?scope=approvals"),
    refetchInterval: 15_000,
  });

  return (
    <div className="stack narrow">
      <h1>{t("approvals.title")}</h1>
      <section className="card">
        {isLoading && <p className="muted">{t("common.loading")}</p>}
        {data && <RequestList items={data} showEmployee empty={t("approvals.empty")} />}
      </section>
    </div>
  );
}
