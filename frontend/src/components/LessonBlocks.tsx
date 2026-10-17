// Содержимое урока из блоков (как в конструкторе сайта). Временный UI — дизайн сделает фронтенд.
import { useTranslation } from "react-i18next";

import type { LessonBlock } from "../api/types";
import Icon from "./Icon";
import { icons } from "./icons";

function Block({ b }: { b: LessonBlock }) {
  const { t } = useTranslation();
  switch (b.type) {
    case "heading":
      return <h2 className="block-heading">{b.text}</h2>;
    case "note":
      return (
        <p className="block-note">
          <Icon src={icons.help} size={18} className="block-note-icon" />
          {b.text}
        </p>
      );
    case "image":
      return (
        <figure className="block-media">
          <img src={b.url} alt={b.text} loading="lazy" />
          {b.text && <figcaption>{b.text}</figcaption>}
        </figure>
      );
    case "video":
      return (
        <figure className="block-media">
          {b.embed_url ? (
            <iframe src={b.embed_url} title={b.text || "video"} allowFullScreen loading="lazy" />
          ) : (
            <video src={b.url} controls preload="metadata" />
          )}
          {b.text && <figcaption>{b.text}</figcaption>}
        </figure>
      );
    case "file":
      return (
        <a className="block-file" href={b.url} target="_blank" rel="noreferrer">
          <span className="block-file-icon" aria-hidden>
            <Icon src={icons.attach} size={22} />
          </span>
          <span>
            <strong>{b.text || b.file_name}</strong>
            <span className="muted small"> · {t("academy.open_media")} <Icon src={icons.externalLink} size={14} /></span>
          </span>
        </a>
      );
    default:
      return <p className="block-text">{b.text}</p>;
  }
}

export default function LessonBlocks({ blocks }: { blocks: LessonBlock[] }) {
  if (blocks.length === 0) return null;
  return (
    <div className="lesson-blocks">
      {blocks.map((b) => (
        <Block key={b.id} b={b} />
      ))}
    </div>
  );
}
