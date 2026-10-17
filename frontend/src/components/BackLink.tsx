import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import Icon from "./Icon";
import { icons } from "./icons";

/** Ссылка «назад» со стрелкой из набора иконок. */
export default function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="muted back-link">
      <Icon src={icons.back} size={16} />
      {children}
    </Link>
  );
}
