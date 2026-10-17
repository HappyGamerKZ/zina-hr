import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { HrRequest, RequestType } from "../api/types";
import RequestList from "../components/RequestList";

export default function RequestsPage() {
  const { t } = useTranslation();
  const [type, setType] = useState<RequestType | "">("");
  const { data, isLoading, error } = useQuery({
    queryKey: ["requests", "my", type],
    queryFn: () => api<HrRequest[]>(`/requests?scope=my${type ? `&type=${type}` : ""}`),
  });

  return (
    <div className="stack">
      <div className="section-head">
        <h1>{t("requests.title")}</h1>
        <div className="row">
          <Link to="/requests/new?type=vacation" className="btn-primary">
            + {t("type.vacation")}
          </Link>
          <Link to="/requests/new?type=advance" className="btn-secondary">
            + {t("type.advance")}
          </Link>
        </div>
      </div>
      <div className="tabs">
        {(["", "vacation", "advance"] as const).map((v) => (
          <button key={v} className={type === v ? "active" : ""} onClick={() => setType(v)}>
            {v ? t(`type.${v}`) : t("common.all")}
          </button>
        ))}
      </div>
      <section className="card">
        {isLoading && <p className="muted">{t("common.loading")}</p>}
        {error && <p className="error">{t("common.error")}</p>}
        {data && <RequestList items={data} empty={t("requests.empty")} />}
      </section>
    </div>
  );
}
