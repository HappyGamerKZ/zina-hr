import { useTranslation } from "react-i18next";

export default function PlaceholderPage({ title }: { title: string }) {
  const { t } = useTranslation();
  return (
    <section className="card narrow">
      <h1>{title}</h1>
      <p className="muted">{t("common.soon")}</p>
    </section>
  );
}
