import type { Metadata } from "next";
import { TermsPage } from "@/features/info/TermsPage";

export const metadata: Metadata = { title: "Terms" };

export default function Page() {
  return <TermsPage />;
}
