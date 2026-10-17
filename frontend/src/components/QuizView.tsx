// Тест Jana Academy: 4 типа вопросов. Временный UI для тестирования backend — дизайн сделает фронтенд.
import { useState, type ReactNode } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Answer, AttemptResult, LessonDetail, QuizQuestion } from "../api/types";
import Icon from "./Icon";
import { icons } from "./icons";

type Quiz = NonNullable<LessonDetail["quiz"]>;
type Answers = Record<string, Answer>;

const BLANK_SPLIT = /(\{\{\d+\}\})/;
const BLANK_MATCH = /^\{\{(\d+)\}\}$/;

function initialAnswers(questions: QuizQuestion[]): Answers {
  // Для «правильного порядка» стартовый порядок уже является ответом
  const a: Answers = {};
  for (const q of questions) if (q.type === "ordering") a[q.id] = q.options.map((o) => o.id);
  return a;
}

function isAnswered(q: QuizQuestion, a: Answer | undefined): boolean {
  if (a === undefined) return false;
  if (q.type === "single") return typeof a === "number";
  if (q.type === "multiple") return Array.isArray(a) && a.length > 0;
  if (q.type === "ordering") return Array.isArray(a);
  const filled = a as Record<string, number>;
  return (q.blanks ?? []).every((b) => filled[String(b)] !== undefined);
}

// --- один вариант / несколько вариантов ---

function ChoiceQuestion({ q, value, onChange }: { q: QuizQuestion; value?: Answer; onChange: (a: Answer) => void }) {
  const multiple = q.type === "multiple";
  const selected = new Set(multiple ? ((value as number[]) ?? []) : value !== undefined ? [value as number] : []);
  const toggle = (id: number) => {
    if (!multiple) return onChange(id);
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange([...next]);
  };
  return (
    <div className="choices">
      {q.options.map((o) => (
        <label key={o.id} className={`choice ${selected.has(o.id) ? "checked" : ""}`}>
          <input
            type={multiple ? "checkbox" : "radio"}
            name={`q${q.id}`}
            checked={selected.has(o.id)}
            onChange={() => toggle(o.id)}
          />
          {o.text}
        </label>
      ))}
    </div>
  );
}

// --- перетаскивание: мышь, палец на телефоне и клавиатура ---

function useDndSensors() {
  return useSensors(
    // Мышь: перетаскивание начинается после сдвига на 6 px, поэтому клики по кнопкам работают
    useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
    // Палец: короткое удержание, чтобы обычная прокрутка страницы не превращалась в перетаскивание
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
}

// --- правильный порядок ---

function SortableRow(props: { id: number; index: number; total: number; text: string; move: (from: number, to: number) => void }) {
  const { id, index, total, text, move } = props;
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? "dragging" : ""}
      {...attributes}
      {...listeners}
    >
      <span className="drag-handle" aria-hidden>
        ⠿
      </span>
      <span className="ordering-text">{text}</span>
      <span className="ordering-buttons">
        <button type="button" className="btn-ghost" onClick={() => move(index, index - 1)} disabled={index === 0} aria-label="up">
          <Icon src={icons.up} size={16} />
        </button>
        <button
          type="button"
          className="btn-ghost"
          onClick={() => move(index, index + 1)}
          disabled={index === total - 1}
          aria-label="down"
        >
          <Icon src={icons.down} size={16} />
        </button>
      </span>
    </li>
  );
}

function OrderingQuestion({ q, value, onChange }: { q: QuizQuestion; value?: Answer; onChange: (a: Answer) => void }) {
  const order = (value as number[]) ?? q.options.map((o) => o.id);
  const text = (id: number) => q.options.find((o) => o.id === id)?.text ?? "";
  const sensors = useDndSensors();

  const move = (from: number, to: number) => {
    if (to < 0 || to >= order.length || from === to) return;
    onChange(arrayMove(order, from, to));
  };

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (over && active.id !== over.id) move(order.indexOf(Number(active.id)), order.indexOf(Number(over.id)));
  };

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
      <SortableContext items={order} strategy={verticalListSortingStrategy}>
        <ol className="ordering">
          {order.map((id, i) => (
            <SortableRow key={id} id={id} index={i} total={order.length} text={text(id)} move={move} />
          ))}
        </ol>
      </SortableContext>
    </DndContext>
  );
}

// --- перетаскивание слов в пропуски ---

type ChipData = { optionId: number; fromBlank?: string };

function DraggableChip({ optionId, fromBlank, label, onClick }: ChipData & { label: string; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: fromBlank ? `blank-chip-${fromBlank}` : `chip-${optionId}`,
    data: { optionId, fromBlank } satisfies ChipData,
  });
  return (
    <span
      ref={setNodeRef}
      className={`chip ${isDragging ? "chip-ghost" : ""}`}
      onClick={onClick}
      {...attributes}
      {...listeners}
    >
      {label}
    </span>
  );
}

function BlankSlot({ blank, children }: { blank: string; children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: `blank-${blank}`, data: { blank } });
  return (
    <span ref={setNodeRef} className={`blank ${isOver ? "over" : ""} ${children ? "filled" : ""}`}>
      {children ?? <span className="blank-number">{blank}</span>}
    </span>
  );
}

function WordBank({ children, label }: { children: ReactNode; label: string }) {
  const { setNodeRef, isOver } = useDroppable({ id: "bank" });
  return (
    <div ref={setNodeRef} className={`word-bank ${isOver ? "over" : ""}`}>
      <span className="muted small">{label}:</span>
      {children}
    </div>
  );
}

function FillBlanksQuestion({ q, value, onChange }: { q: QuizQuestion; value?: Answer; onChange: (a: Answer) => void }) {
  const { t } = useTranslation();
  const sensors = useDndSensors();
  const [dragging, setDragging] = useState<ChipData | null>(null);
  const filled = (value as Record<string, number>) ?? {};
  const used = new Set(Object.values(filled));
  const bank = q.options.filter((o) => !used.has(o.id));
  const text = (id: number) => q.options.find((o) => o.id === id)?.text ?? "";

  const place = (optionId: number, blank: string, fromBlank?: string) => {
    const next = { ...filled };
    const displaced = next[blank];
    next[blank] = optionId;
    if (fromBlank && fromBlank !== blank) {
      if (displaced !== undefined) next[fromBlank] = displaced; // поменять слова местами
      else delete next[fromBlank];
    }
    onChange(next);
  };

  const clearBlank = (blank: string) => {
    const next = { ...filled };
    delete next[blank];
    onChange(next);
  };

  // Клик по слову — в первый пустой пропуск; клик по слову в пропуске — вернуть его в банк слов
  const placeByClick = (optionId: number) => {
    const empty = (q.blanks ?? []).map(String).find((b) => filled[b] === undefined);
    if (empty) place(optionId, empty);
  };

  const onDragStart = ({ active }: DragStartEvent) => setDragging(active.data.current as ChipData);
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    setDragging(null);
    const data = active.data.current as ChipData;
    if (!over || !data) return;
    const blank = over.data.current?.blank as string | undefined;
    if (blank) place(data.optionId, blank, data.fromBlank);
    else if (over.id === "bank" && data.fromBlank) clearBlank(data.fromBlank);
  };

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}>
      <p className="fill-text">
        {q.text.split(BLANK_SPLIT).map((part, i) => {
          const m = part.match(BLANK_MATCH);
          if (!m) return <span key={i}>{part}</span>;
          const blank = m[1];
          const optionId = filled[blank];
          return (
            <BlankSlot key={i} blank={blank}>
              {optionId !== undefined ? (
                <DraggableChip optionId={optionId} fromBlank={blank} label={text(optionId)} onClick={() => clearBlank(blank)} />
              ) : null}
            </BlankSlot>
          );
        })}
      </p>
      <WordBank label={t("academy.word_bank")}>
        {bank.map((o) => (
          <DraggableChip key={o.id} optionId={o.id} label={o.text} onClick={() => placeByClick(o.id)} />
        ))}
      </WordBank>
      <DragOverlay>{dragging ? <span className="chip chip-overlay">{text(dragging.optionId)}</span> : null}</DragOverlay>
    </DndContext>
  );
}

// --- ответ в читаемом виде (для разбора результата) ---

function AnswerText({ q, answer }: { q: QuizQuestion; answer: Answer }) {
  const text = (id: number) => q.options.find((o) => o.id === id)?.text ?? "?";
  if (q.type === "single") return <>{text(answer as number)}</>;
  if (q.type === "multiple") return <>{(answer as number[]).map(text).join(", ")}</>;
  if (q.type === "ordering")
    return (
      <ol className="answer-list">
        {(answer as number[]).map((id) => (
          <li key={id}>{text(id)}</li>
        ))}
      </ol>
    );
  const filled = answer as Record<string, number>;
  return (
    <>
      {q.text.split(BLANK_SPLIT).map((part, i) => {
        const m = part.match(BLANK_MATCH);
        return m ? <strong key={i}>{filled[m[1]] !== undefined ? text(filled[m[1]]) : "___"}</strong> : part;
      })}
    </>
  );
}

const HINT: Record<QuizQuestion["type"], string> = {
  single: "academy.q_single",
  multiple: "academy.q_multiple",
  ordering: "academy.q_ordering",
  fill_blanks: "academy.q_fill",
};

export default function QuizView({ assignmentId, quiz }: { assignmentId: number; quiz: Quiz }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const finished = quiz.passed || quiz.attempts_left === 0;
  const [answers, setAnswers] = useState<Answers>(() => initialAnswers(quiz.questions));
  const [result, setResult] = useState<AttemptResult | null>(finished ? quiz.last_attempt : null);
  const [warning, setWarning] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: () =>
      api<AttemptResult>(`/academy/assignments/${assignmentId}/quizzes/${quiz.id}/attempts`, {
        method: "POST",
        body: { answers },
      }),
    onSuccess: (res) => {
      setResult(res);
      window.scrollTo({ top: 0, behavior: "smooth" });
      qc.invalidateQueries({ queryKey: ["academy"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
    },
  });

  const onSubmit = () => {
    if (!quiz.questions.every((q) => isAnswered(q, answers[q.id]))) {
      setWarning(t("academy.answer_all"));
      return;
    }
    setWarning(null);
    submit.mutate();
  };

  const left = result ? result.attempts_left : quiz.attempts_left;
  const leftText = left === null ? t("academy.unlimited") : String(left);

  if (result) {
    const byId = new Map(result.details.map((d) => [d.question_id, d]));
    return (
      <div className="stack">
        <div className={`card quiz-result ${result.passed ? "ok" : "bad"}`}>
          <h2>
            {result.passed
              ? t("academy.passed", { score: result.score })
              : t("academy.failed", { score: result.score, pass: result.pass_score })}
          </h2>
          {!result.passed && left === 0 && <p>{t("academy.no_attempts")}</p>}
          {!result.answers_revealed && <p className="muted small">{t("academy.hidden_answers")}</p>}
          {!result.passed && left !== 0 && (
            <button
              className="btn-primary"
              onClick={() => {
                setResult(null);
                setAnswers(initialAnswers(quiz.questions));
              }}
            >
              {t("academy.retry")} ({t("academy.quiz_info", { pass: quiz.pass_score, left: leftText })})
            </button>
          )}
        </div>
        {quiz.questions.map((q, i) => {
          const d = byId.get(q.id);
          const verdict = !d ? "" : d.correct ? "correct" : d.fraction > 0 ? "partial" : "wrong";
          return (
            <section key={q.id} className={`card question verdict-${verdict}`}>
              <div className="section-head">
                <strong>
                  {i + 1}. {q.type === "fill_blanks" ? q.text.replace(/\{\{\d+\}\}/g, "___") : q.text}
                </strong>
                {verdict && <span className={`status status-${verdict === "correct" ? "ok" : verdict === "partial" ? "warn" : "bad"}`}>{t(`academy.${verdict}`)}</span>}
              </div>
              {d?.correct_answer !== undefined && (
                <div className="small">
                  <span className="muted">{t("academy.correct_answer")}: </span>
                  <AnswerText q={q} answer={d.correct_answer} />
                  {d.explanation && <p className="muted">{d.explanation}</p>}
                </div>
              )}
            </section>
          );
        })}
      </div>
    );
  }

  return (
    <div className="stack">
      <p className="hint">{t("academy.quiz_info", { pass: quiz.pass_score, left: leftText })}</p>
      {quiz.questions.map((q, i) => (
        <section key={q.id} className="card question">
          <strong>{i + 1}. {q.type === "fill_blanks" ? null : q.text}</strong>
          <p className="muted small">{t(HINT[q.type])}</p>
          {(q.type === "single" || q.type === "multiple") && (
            <ChoiceQuestion q={q} value={answers[q.id]} onChange={(a) => setAnswers({ ...answers, [q.id]: a })} />
          )}
          {q.type === "ordering" && (
            <OrderingQuestion q={q} value={answers[q.id]} onChange={(a) => setAnswers({ ...answers, [q.id]: a })} />
          )}
          {q.type === "fill_blanks" && (
            <FillBlanksQuestion q={q} value={answers[q.id]} onChange={(a) => setAnswers({ ...answers, [q.id]: a })} />
          )}
        </section>
      ))}
      {warning && <p className="error">{warning}</p>}
      {submit.error && <p className="error">{submit.error.message}</p>}
      <div>
        <button className="btn-primary" onClick={onSubmit} disabled={submit.isPending}>
          {t("academy.submit_quiz")}
        </button>
      </div>
    </div>
  );
}
