import type { Metadata } from "next";
import { ResetPasswordForm } from "@/features/auth/ResetPasswordForm";

// The key is a single-use secret in the address: keep it out of search results and Referer headers.
export const metadata: Metadata = {
  title: "Create new password",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function Page({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  return <ResetPasswordForm keyParam={key} />;
}
