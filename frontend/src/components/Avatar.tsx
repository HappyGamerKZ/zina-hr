/** Аватар по инициалам (фото сотрудников в прототипе не храним). ФИО: «Фамилия Имя Отчество». */
export default function Avatar({ name, size = 56 }: { name: string; size?: number }) {
  const [last = "", first = ""] = name.split(" ");
  const initials = (first[0] ?? "") + (last[0] ?? "");
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.36 }} aria-hidden>
      {initials.toUpperCase() || "?"}
    </span>
  );
}
