"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { ApiError } from "@/lib/api/client";
import { requestPasswordReset } from "@/lib/auth/auth-api";
import { bannerMessage } from "./messages";

function emailError(email: string): string | undefined {
  if (!email.trim()) return "Enter your email address.";
  if (!/^[^\s@]+@[^\s@]+$/.test(email.trim())) return "Enter a valid email address.";
  return undefined;
}

/**
 * `/forgot-password` (Stitch a5). The idle form and the "sent" message are separate states, and
 * the sent text is identical whether or not an account exists (no enumeration), so it only echoes
 * what the visitor typed. Without a5's "Secured Node", "Protocol standard" and enumeration notice
 * (ANALYSIS b-5).
 */
export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [banner, setBanner] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const error = emailError(email);
    setFieldError(error);
    setBanner(null);
    if (error) return;

    const typed = email.trim();
    setSubmitting(true);
    try {
      await requestPasswordReset(typed);
      setSentTo(typed);
    } catch (caught) {
      const serverError =
        caught instanceof ApiError && caught.status === 400
          ? caught.fieldErrors.email?.[0]
          : undefined;
      if (serverError) setFieldError(serverError);
      else setBanner(bannerMessage(caught));
    } finally {
      setSubmitting(false);
    }
  }

  if (sentTo !== null) return <Sent email={sentTo} onAgain={() => setSentTo(null)} />;

  return (
    <>
      <div className="mb-space-lg text-center">
        <h1 className="font-headline-md text-headline-md text-on-surface">Reset your password</h1>
        <p className="mx-auto mt-space-xs max-w-sm font-body-md text-body-md text-on-surface-variant">
          Enter the email address of your account and we&apos;ll send you a link to choose a new
          password.
        </p>
      </div>

      {banner && (
        <Alert tone="error" onDismiss={() => setBanner(null)} className="mb-space-lg">
          <p className="font-medium">{banner}</p>
        </Alert>
      )}

      <form className="space-y-space-md" noValidate onSubmit={onSubmit}>
        <TextField
          label="Email address"
          type="email"
          name="email"
          autoComplete="email"
          placeholder="name@domain.com"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={fieldError}
        />
        <Button type="submit" block loading={submitting}>
          <span>Send reset link</span>
          <span aria-hidden="true" className="leading-none tracking-normal">
            →
          </span>
        </Button>
      </form>

      <div className="mt-space-lg w-full rounded-lg bg-surface-container-low py-space-md text-center">
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Remembered your password?{" "}
          <Link href="/login" className="ml-0.5 font-medium text-secondary hover:underline">
            Back to log in
          </Link>
        </p>
      </div>
    </>
  );
}

function Sent({ email, onAgain }: { email: string; onAgain: () => void }) {
  return (
    <div className="text-center">
      <h1 className="mb-space-md font-headline-md text-headline-md text-on-surface">
        Check your inbox
      </h1>
      <Alert tone="info" title="Reset link on its way" className="mb-space-lg text-left">
        If an account exists for <span className="font-semibold break-words">{email}</span>,
        we&apos;ve sent a link to reset your password. It expires in 24 hours.
      </Alert>
      <p className="mx-auto mb-space-lg max-w-xs font-body-sm text-body-sm text-outline">
        Be sure to check your spam or junk folder if you don&apos;t see it in a few minutes.
      </p>
      <div className="flex flex-col items-center gap-space-sm">
        <Link
          href="/login"
          className="font-body-md text-body-md font-medium text-secondary hover:underline"
        >
          Back to log in
        </Link>
        <Button variant="ghost" onClick={onAgain}>
          Use a different email
        </Button>
      </div>
    </div>
  );
}
