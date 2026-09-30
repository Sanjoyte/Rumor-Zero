import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { UiGallery } from "@/features/dev/UiGallery";

export const metadata: Metadata = {
  title: "UI gallery",
  robots: { index: false, follow: false },
};

/** Development-only: a production build answers 404 for this route. */
export default function DevUiPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <UiGallery />;
}
