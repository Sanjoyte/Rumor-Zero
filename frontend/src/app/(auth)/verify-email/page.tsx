import type { Metadata } from "next";
import { VerifyEmailPending } from "@/features/auth/VerifyEmailPending";

export const metadata: Metadata = { title: "Verify your email" };

export default function Page() {
  return <VerifyEmailPending />;
}
