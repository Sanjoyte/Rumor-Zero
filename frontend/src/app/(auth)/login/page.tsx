import type { Metadata } from "next";
import { LoginForm } from "@/features/auth/LoginForm";

export const metadata: Metadata = { title: "Log in" };

export default function Page() {
  return <LoginForm />;
}
