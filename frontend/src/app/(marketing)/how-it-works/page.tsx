import type { Metadata } from "next";
import { HowItWorks } from "@/features/info/HowItWorks";

export const metadata: Metadata = { title: "How verification works" };

export default function Page() {
  return <HowItWorks />;
}
