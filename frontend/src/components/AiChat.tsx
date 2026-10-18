// AI Jana: общий чат для страницы «AI Jana» и всплывающего окна (круглая кнопка внизу справа).
// Состояние живёт в провайдере внутри Layout, поэтому переписка не пропадает при переходе между
// страницами, а копия в sessionStorage переживает перезагрузку вкладки. У каждого пользователя своя
// переписка; при выходе она стирается.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";
import type { AiAnswer, HrRequestDetail } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { fmtDate } from "../i18n";
import Icon from "./Icon";
import { icons } from "./icons";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  reply?: AiAnswer;
  question?: string; // для ответа: на какой вопрос (для «Передать в HR»)
  error?: boolean;
  escalated?: boolean;
}

interface ChatState {
  messages: ChatMessage[];
  pending: boolean;
  send: (question: string) => void;
  escalate: (index: number) => void;
  clear: () => void;
}

const ChatContext = createContext<ChatState | null>(null);
const STORAGE_PREFIX = "ai-chat:";

function load(key: string): ChatMessage[] {
  try {
    return JSON.parse(sessionStorage.getItem(key) ?? "[]") as ChatMessage[];
  } catch {
    return [];
  }
}

/** Стереть переписку AI Jana в этой вкладке (при выходе из системы). */
export function clearStoredChats() {
  try {
    Object.keys(sessionStorage)
      .filter((k) => k.startsWith(STORAGE_PREFIX))
      .forEach((k) => sessionStorage.removeItem(k));
  } catch {
    /* хранилище недоступно — нечего чистить */
  }
}

export function AiChatProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { me } = useAuth();
  const qc = useQueryClient();
  const key = `${STORAGE_PREFIX}${me?.id ?? "anon"}`;
  const [messages, setMessages] = useState<ChatMessage[]>(() => load(key));
  const [pending, setPending] = useState(false);

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(messages.slice(-40)));
    } catch {
      /* приватный режим или переполнение — работаем без сохранения */
    }
  }, [key, messages]);

  const send = useCallback(
    (question: string) => {
      const q = question.trim();
      if (!q || pending) return;
      const history = messages.slice(-4).map((m) => ({ role: m.role, content: m.content }));
      setMessages((list) => [...list, { role: "user", content: q }]);
      setPending(true);
      api<AiAnswer>("/ai/ask", { method: "POST", body: { question: q, history } })
        .then((reply) => setMessages((list) => [...list, { role: "assistant", content: reply.answer, reply, question: q }]))
        .catch((err) =>
          setMessages((list) => [
            ...list,
            {
              role: "assistant",
              content: err instanceof ApiError && err.status === 503 ? t("ai.unavailable") : String(err?.message ?? err),
              question: q,
              error: true,
            },
          ]),
        )
        .finally(() => setPending(false));
    },
    [messages, pending, t],
  );

  const escalate = useCallback(
    (index: number) => {
      const m = messages[index];
      if (!m?.question) return;
      api("/ai/escalate", { method: "POST", body: { question: m.question, ai_answer: m.error ? "" : m.content } }).then(() => {
        setMessages((list) => list.map((x, i) => (i === index ? { ...x, escalated: true } : x)));
        qc.invalidateQueries({ queryKey: ["ai", "questions"] });
      });
    },
    [messages, qc],
  );

  const clear = useCallback(() => setMessages([]), []);

  return <ChatContext.Provider value={{ messages, pending, send, escalate, clear }}>{children}</ChatContext.Provider>;
}

export function useAiChat(): ChatState {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useAiChat — только внутри AiChatProvider");
  return ctx;
}

function AssistantBubble({ m, onEscalate }: { m: ChatMessage; onEscalate: () => void }) {
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

/** Переписка + поле ввода. compact — для всплывающего окна. */
export function ChatPanel({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  const { messages, pending, send, escalate } = useAiChat();
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // без return: в новых браузерах scrollIntoView возвращает Promise, а React ждёт из эффекта функцию очистки
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, pending]);

  const submit = (value: string) => {
    if (!value.trim() || pending) return;
    send(value);
    setText("");
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(text);
  };

  return (
    <div className={`chat${compact ? " chat-compact" : " card"}`}>
      <div className="chat-log">
        {messages.length === 0 && (
          <div className="chat-empty">
            <span className="muted small">{t("ai.suggestions")}:</span>
            <div className="row">
              {(["s1", "s2", "s3", "s4"] as const).map((k) => (
                <button key={k} className="chip-btn" onClick={() => submit(t(`ai.${k}`))}>
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
            <AssistantBubble key={i} m={m} onEscalate={() => escalate(i)} />
          ),
        )}
        {pending && <div className="bubble bubble-ai bubble-thinking">{t("ai.thinking")}</div>}
        <div ref={endRef} />
      </div>
      <form className="chat-input" onSubmit={onSubmit}>
        <textarea
          rows={compact ? 1 : 2}
          value={text}
          maxLength={1000}
          placeholder={t("ai.placeholder")}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit(text);
            }
          }}
        />
        <button className="btn-primary" disabled={!text.trim() || pending} aria-label={t("ai.send")}>
          <Icon src={icons.forward} size={18} />
          {!compact && t("ai.send")}
        </button>
      </form>
    </div>
  );
}

/** Всплывающее окно чата по круглой кнопке. Переписка та же, что на странице «AI Jana». */
export function AiPopup({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { messages, clear } = useAiChat();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <section className="ai-popup" role="dialog" aria-label={t("ai.title")}>
      <header className="ai-popup-head">
        <strong className="icon-title">
          <Icon src={icons.ai} size={20} />
          {t("ai.title")}
        </strong>
        <span className="row">
          {messages.length > 0 && (
            <button className="btn-ghost btn-small" onClick={clear}>
              {t("ai.clear")}
            </button>
          )}
          <button className="btn-ghost btn-small" onClick={() => navigate("/ai")} title={t("ai.open_full")}
                  aria-label={t("ai.open_full")}>
            <Icon src={icons.externalLink} size={16} />
          </button>
          <button className="btn-ghost btn-small" onClick={onClose} aria-label={t("ai.close")}>
            <Icon src={icons.close} size={16} />
          </button>
        </span>
      </header>
      <ChatPanel compact />
    </section>
  );
}
