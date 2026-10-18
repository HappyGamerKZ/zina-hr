// AI Jana: страница чата. Переписка общая со всплывающим окном (components/AiChat.tsx).
// Временный UI для тестирования backend — дизайн сделает фронтенд.
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { AiQuestion } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ChatPanel, useAiChat } from "../components/AiChat";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import { fmtDateTime } from "../i18n";

function MyQuestions() {
  const { t } = useTranslation();
  const { data } = useQuery({ queryKey: ["ai", "questions"], queryFn: () => api<AiQuestion[]>("/ai/questions") });
  if (!data?.length) return null;
  return (
    <section className="card">
      <h2>{t("ai.my_questions")}</h2>
      <ul className="request-list">
        {data.map((q) => (
          <li key={q.id} className="ai-question">
            <div className="section-head">
              <strong>{q.question}</strong>
              <span className={`status status-${q.status === "open" ? "warn" : "ok"}`}>
                {q.status === "open" ? t("ai.status_open") : t("ai.status_answered")}
              </span>
            </div>
            {q.hr_answer && (
              <p className="small">
                <strong>{t("ai.hr_answer")}:</strong> {q.hr_answer}
              </p>
            )}
            <span className="muted small">{fmtDateTime(q.created_at)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function AiPage() {
  const { t } = useTranslation();
  const { me } = useAuth();
  const { messages, clear } = useAiChat();

  return (
    <div className="stack">
      <div className="section-head">
        <div>
          <h1 className="icon-title">
            <Icon src={icons.ai} size={26} />
            {t("ai.title")}
          </h1>
          <p className="muted page-sub">{t("ai.subtitle")}</p>
        </div>
        <div className="row">
          {me?.role === "hr_admin" ? (
            <Link to="/ai/questions" className="btn-secondary">
              <Icon src={icons.messages} size={18} />
              {t("ai.hr_questions")}
            </Link>
          ) : null}
          {messages.length > 0 && (
            <button className="btn-ghost" onClick={clear}>
              {t("ai.clear")}
            </button>
          )}
        </div>
      </div>

      <ChatPanel />

      <MyQuestions />
    </div>
  );
}
