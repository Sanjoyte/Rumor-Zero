import type { Metadata } from "next";
import { PrivacyPage } from "@/features/info/PrivacyPage";

export const metadata: Metadata = { title: "Privacy" };

export default function Page() {
  return <PrivacyPage />;
}
