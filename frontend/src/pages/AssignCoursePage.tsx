import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "../api/client";
import type { Assignment, CourseListItem, TeamMember } from "../api/types";
import BackLink from "../components/BackLink";
import Icon from "../components/Icon";
import { icons } from "../components/icons";
import { useCourseTitle } from "../components/academy";

export default function AssignCoursePage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const title = useCourseTitle();
  const courses = useQuery({ queryKey: ["academy", "courses"], queryFn: () => api<CourseListItem[]>("/academy/courses") });
  const team = useQuery({ queryKey: ["team"], queryFn: () => api<TeamMember[]>("/team") });
  const teamAssignments = useQuery({
    queryKey: ["academy", "assignments", "team"],
    queryFn: () => api<Assignment[]>("/academy/assignments?scope=team"),
  });

  const [courseId, setCourseId] = useState<number | "">("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [due, setDue] = useState("");
  const [done, setDone] = useState<number | null>(null);

  const existing = (employeeId: number) =>
    teamAssignments.data?.find((a) => a.employee.id === employeeId && a.course.id === courseId);
  // Курс в работе — назначать нельзя; завершён или не сдан — назначится повторно (новое прохождение)
  const alreadyHas = (employeeId: number) => {
    const a = existing(employeeId);
    return !!a && (a.status === "assigned" || a.status === "in_progress");
  };
  const willReassign = (employeeId: number) => {
    const a = existing(employeeId);
    return !!a && (a.status === "completed" || a.status === "failed");
  };

  const assign = useMutation({
    mutationFn: () =>
      api<Assignment[]>("/academy/assignments", {
        method: "POST",
        body: { course_id: courseId, employee_ids: [...selected], due_date: due || null },
      }),
    onSuccess: (created) => {
      setDone(created.length);
      setSelected(new Set());
      qc.invalidateQueries({ queryKey: ["academy"] });
    },
  });

  const toggle = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    assign.mutate();
  };

  return (
    <div className="stack narrow">
      <BackLink to="/academy?tab=team">{t("academy.tab_team")}</BackLink>
      <form className="card form" onSubmit={onSubmit}>
        <h1>{t("academy.assign_title")}</h1>
        <label>
          {t("academy.course")}
          <select value={courseId} onChange={(e) => setCourseId(e.target.value ? Number(e.target.value) : "")} required>
            <option value="">—</option>
            {courses.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {title(c)}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="employee-picker">
          <legend>{t("academy.employees")}</legend>
          {team.data?.map((m) => (
            <label key={m.id} className="choice">
              <input
                type="checkbox"
                checked={selected.has(m.id)}
                disabled={alreadyHas(m.id)}
                onChange={() => toggle(m.id)}
              />
              {m.full_name} <span className="muted small">· {m.position}</span>
              {alreadyHas(m.id) && <span className="muted small"> · {t("academy.already_assigned")}</span>}
              {willReassign(m.id) && <span className="muted small"> · {t("academy.will_reassign")}</span>}
            </label>
          ))}
        </fieldset>
        <label>
          {t("academy.due_date")}
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        {assign.error && <p className="error">{assign.error.message}</p>}
        {done !== null && <p className="hint icon-link">
            <Icon src={icons.done} size={16} />
            {t("academy.assigned_ok", { count: done })}
          </p>}
        <div>
          <button className="btn-primary" disabled={assign.isPending || !courseId || selected.size === 0}>
            {t("academy.assign_submit")}
          </button>
        </div>
      </form>
    </div>
  );
}
