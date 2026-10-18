// AI Jana: чат по базе знаний. Временный UI для тестирования backend — дизайн сделает фронтенд.
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";
import type { AiAnswer, AiQuestion, HrRequestDetail } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import { fmtDate, fmtDateTime } from "../i18n";

interface Message {
  role: "user" | "assistant";
  content: string;
  reply?: AiAnswer;
  question?: string; // для ответа: на какой вопрос (для «Передать в HR»)
  error?: boolean;
  escalated?: boolean;
}

function AssistantBubble({ m, onEscalate }: { m: Message; onEscalate: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const draft = m.reply?.draft;
  const createDraft = useMutation({
    mutationFn: () =>
      api<HrRequestDetail>("/requests", {
        method: "POST",
        body: { type: "vacation", vacation: { date_from: draft!.date_from, date_to: draft!.date_to }, as_draft: true },
      }),
    onSuccess: (req) => {
      qc.invalidateQueries({ queryKey: ["requests"] });
      navigate(`/requests/${req.id}`);
    },
  });
  return (
    <div className="bubble bubble-ai">
      <p className="bubble-text">{m.content}</p>
      {m.reply && m.reply.sources.length > 0 && (
        <div className="ai-sources">
          {m.reply.sources.map((s) => (
            <span key={s.id} className="ai-source">
              <Icon src={icons.documents} size={14} />
              {t("ai.source")}: {s.id} · {s.title}
            </span>
          ))}
        </div>
      )}
      {draft && (
        <div className="ai-draft">
          <strong>
            {fmtDate(draft.date_from)} – {fmtDate(draft.date_to)} · {t("common.days", { count: draft.days })}
          </strong>
          <span className="muted small">{t("ai.draft_hint")}</span>
          {createDraft.error && <span className="error small">{createDraft.error.message}</span>}
          <button className="btn-primary btn-small" disabled={createDraft.isPending} onClick={() => createDraft.mutate()}>
            <Icon src={icons.vacation} size={16} />
            {t("ai.draft_create")}
          </button>
        </div>
      )}
      {(m.reply?.can_escalate || m.error) && !m.escalated && (
        <button className="btn-secondary btn-small" onClick={onEscalate}>
          <Icon src={icons.messages} size={16} />
          {t("ai.escalate")}
        </button>
      )}
      {m.escalated && <p className="hint small">{t("ai.escalated")}</p>}
    </div>
  );
}

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
  const qc = useQueryClient();
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // без return: в новых браузерах scrollIntoView возвращает Promise, а React ждёт из эффекта функцию очистки
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const ask = useMutation({
    mutationFn: (question: string) =>
      api<AiAnswer>("/ai/ask", {
        method: "POST",
        body: {
          question,
          history: messages.slice(-4).map((m) => ({ role: m.role, content: m.content })),
        },
      }),
    onSuccess: (reply, question) =>
      setMessages((list) => [...list, { role: "assistant", content: reply.answer, reply, question }]),
    onError: (err, question) =>
      setMessages((list) => [
        ...list,
        {
          role: "assistant",
          content: err instanceof ApiError && err.status === 503 ? t("ai.unavailable") : err.message,
          question,
          error: true,
        },
      ]),
  });

  const escalate = useMutation({
    mutationFn: ({ index }: { index: number }) =>
      api("/ai/escalate", {
        method: "POST",
        body: { question: messages[index].question, ai_answer: messages[index].error ? "" : messages[index].content },
      }),
    onSuccess: (_, { index }) => {
      setMessages((list) => list.map((m, i) => (i === index ? { ...m, escalated: true } : m)));
      qc.invalidateQueries({ queryKey: ["ai", "questions"] });
    },
  });

  const send = (question: string) => {
    const q = question.trim();
    if (!q || ask.isPending) return;
    setMessages((list) => [...list, { role: "user", content: q }]);
    setText("");
    ask.mutate(q);
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(text);
  };

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
            <button className="btn-ghost" onClick={() => setMessages([])}>
              {t("ai.clear")}
            </button>
          )}
        </div>
      </div>

      <section className="card chat">
        <div className="chat-log">
          {messages.length === 0 && (
            <div className="chat-empty">
              <span className="muted small">{t("ai.suggestions")}:</span>
              <div className="row">
                {(["s1", "s2", "s3", "s4"] as const).map((k) => (
                  <button key={k} className="chip-btn" onClick={() => send(t(`ai.${k}`))}>
                    {t(`ai.${k}`)}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="bubble bubble-user">
                {m.content}
              </div>
            ) : (
              <AssistantBubble key={i} m={m} onEscalate={() => escalate.mutate({ index: i })} />
            ),
          )}
          {ask.isPending && <div className="bubble bubble-ai bubble-thinking">{t("ai.thinking")}</div>}
          <div ref={endRef} />
        </div>
        <form className="chat-input" onSubmit={onSubmit}>
          <textarea
            rows={2}
            value={text}
            maxLength={1000}
            placeholder={t("ai.placeholder")}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(text);
              }
            }}
          />
          <button className="btn-primary" disabled={!text.trim() || ask.isPending} aria-label={t("ai.send")}>
            <Icon src={icons.forward} size={18} />
            {t("ai.send")}
          </button>
        </form>
      </section>

      <MyQuestions />
    </div>
  );
}
