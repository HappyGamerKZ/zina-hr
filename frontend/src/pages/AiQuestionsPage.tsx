// HR: вопросы, которые сотрудники передали из AI Jana. Ответ уходит сотруднику уведомлением.
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { AiQuestion } from "../api/types";
import BackLink from "../components/BackLink";
import { EmptyState } from "../components/Illustration";
import { fmtDateTime } from "../i18n";

function QuestionCard({ q }: { q: AiQuestion }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const answer = useMutation({
    mutationFn: () => api(`/ai/questions/${q.id}/answer`, { method: "POST", body: { answer: text } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai", "questions"] }),
  });
  return (
    <section className="card stack" style={{ gap: 8 }}>
      <div className="section-head">
        <strong>{q.author}</strong>
        <span className={`status status-${q.status === "open" ? "warn" : "ok"}`}>
          {q.status === "open" ? t("ai.status_open") : t("ai.status_answered")}
        </span>
      </div>
      <p className="block-text">{q.question}</p>
      <span className="muted small">{fmtDateTime(q.created_at)}</span>
      {q.ai_answer && (
        <details>
          <summary className="small muted">{t("ai.ai_tried")}</summary>
          <p className="small block-text">{q.ai_answer}</p>
        </details>
      )}
      {q.status === "answered" ? (
        <p className="small">
          <strong>{t("ai.hr_answer")}</strong> ({q.answered_by}): {q.hr_answer}
        </p>
      ) : (
        <>
          <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder={t("ai.answer_placeholder")} />
          {answer.error && <p className="error">{answer.error.message}</p>}
          <div>
            <button className="btn-primary" disabled={!text.trim() || answer.isPending} onClick={() => answer.mutate()}>
              {t("ai.answer_send")}
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export default function AiQuestionsPage() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({ queryKey: ["ai", "questions"], queryFn: () => api<AiQuestion[]>("/ai/questions") });
  return (
    <div className="stack narrow">
      <BackLink to="/ai">{t("ai.title")}</BackLink>
      <div>
        <h1>{t("ai.hr_questions")}</h1>
        <p className="muted page-sub">{t("ai.hr_questions_sub")}</p>
      </div>
      {isLoading && <p className="muted">{t("common.loading")}</p>}
      {data?.length === 0 && <EmptyState name="chat" text={t("ai.no_questions")} />}
      {data?.map((q) => <QuestionCard key={q.id} q={q} />)}
    </div>
  );
}
