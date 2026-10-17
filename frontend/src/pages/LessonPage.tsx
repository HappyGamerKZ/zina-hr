import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, ApiError } from "../api/client";
import type { LessonDetail } from "../api/types";
import BackLink from "../components/BackLink";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import LessonBlocks from "../components/LessonBlocks";
import QuizView from "../components/QuizView";

export default function LessonPage() {
  const { id, lessonId } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const base = `/academy/assignments/${id}`;

  const { data: lesson, isLoading, error } = useQuery({
    queryKey: ["academy", "lesson", id, lessonId],
    queryFn: () => api<LessonDetail>(`${base}/lessons/${lessonId}`),
    retry: false,
  });

  const complete = useMutation({
    mutationFn: () => api(`${base}/lessons/${lessonId}/complete`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["academy"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["profile"] });
      navigate(lesson?.next_lesson_id ? `${base}/lessons/${lesson.next_lesson_id}` : base);
    },
  });

  if (isLoading) return <p className="muted">{t("common.loading")}</p>;
  if (error instanceof ApiError && error.status === 403)
    return (
      <div className="stack narrow">
        <BackLink to={base}>{t("academy.back_to_course")}</BackLink>
        <p className="error">{error.message}</p>
      </div>
    );
  if (error || !lesson) return <p className="error">{t("common.error")}</p>;

  return (
    <div className="stack narrow">
      <BackLink to={base}>{t("academy.back_to_course")}</BackLink>
      <section className="card">
        <span className="muted small">
          {lesson.module} · {t(`academy.kind.${lesson.type}`)}
        </span>
        <h1>{lesson.title}</h1>
        <LessonBlocks blocks={lesson.blocks} />
        {lesson.type !== "quiz" && (
          <div className="row">
            {lesson.completed ? (
              <span className="status status-ok">
                <Icon src={icons.done} size={14} /> {t("academy.completed")}
              </span>
            ) : (
              <button className="btn-primary" onClick={() => complete.mutate()} disabled={complete.isPending}>
                {t("academy.mark_done")}
              </button>
            )}
            {complete.error && <p className="error">{complete.error.message}</p>}
          </div>
        )}
      </section>

      {lesson.quiz && <QuizView key={lesson.id} assignmentId={Number(id)} quiz={lesson.quiz} />}

      <div className="row lesson-nav">
        {lesson.prev_lesson_id && (
          <Link to={`${base}/lessons/${lesson.prev_lesson_id}`} className="btn-ghost">
            <Icon src={icons.back} size={16} />
            {t("academy.prev")}
          </Link>
        )}
        {lesson.next_lesson_id && lesson.completed && (
          <Link to={`${base}/lessons/${lesson.next_lesson_id}`} className="btn-ghost">
            {t("academy.next")}
            <Icon src={icons.forward} size={16} />
          </Link>
        )}
      </div>
    </div>
  );
}
