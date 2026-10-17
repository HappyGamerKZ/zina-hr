import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Notification } from "../api/types";
import { fmtDateTime } from "../i18n";

export default function NotificationsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => api<Notification[]>("/notifications"),
    refetchInterval: 15_000,
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["notifications"] });
  const readAll = useMutation({ mutationFn: () => api("/notifications/read-all", { method: "POST" }), onSuccess: refresh });
  const readOne = useMutation({
    mutationFn: (id: number) => api(`/notifications/${id}/read`, { method: "POST" }),
    onSuccess: refresh,
  });

  return (
    <div className="stack narrow">
      <div className="section-head">
        <h1>{t("notifications.title")}</h1>
        <button className="btn-ghost" onClick={() => readAll.mutate()}>
          {t("notifications.read_all")}
        </button>
      </div>
      <section className="card">
        {isLoading && <p className="muted">{t("common.loading")}</p>}
        {data?.length === 0 && <p className="muted">{t("notifications.empty")}</p>}
        <ul className="note-list">
          {data?.map((n) => (
            <li key={n.id} className={n.is_read ? "" : "unread"}>
              <Link to={n.link || "/notifications"} onClick={() => !n.is_read && readOne.mutate(n.id)}>
                <strong>{n.title}</strong>
                {n.body && <span className="small">{n.body}</span>}
                <span className="muted small">{fmtDateTime(n.created_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
