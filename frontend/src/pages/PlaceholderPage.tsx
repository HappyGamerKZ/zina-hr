import { useTranslation } from "react-i18next";

import { EmptyState } from "../components/Illustration";

export default function PlaceholderPage({ title }: { title: string }) {
  const { t } = useTranslation();
  return (
    <section className="card narrow">
      <h1>{title}</h1>
      <EmptyState name="chat" text={t("common.soon")} />
    </section>
  );
}
