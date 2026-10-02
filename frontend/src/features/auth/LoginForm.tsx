"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { PasswordField } from "@/components/ui/PasswordField";
import { TextField } from "@/components/ui/TextField";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { bannerMessage } from "./messages";
import { useRedirectWhenLoggedIn } from "./useRedirectWhenLoggedIn";

interface FieldErrors {
  email?: string;
  password?: string;
}

function validate(email: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!email.trim()) errors.email = "Enter your email address.";
  else if (!/^[^\s@]+@[^\s@]+$/.test(email.trim())) errors.email = "Enter a valid email address.";
  if (!password) errors.password = "Enter your password.";
  return errors;
}

/**
 * `/login` (Stitch a3). One dismissible banner for failures; no "Remember me" and no attempt
 * counter (ANALYSIS b-2). "Forgot password?" arrives with its page in Part 2, Google in Part 3.
 */
export function LoginForm() {
  const { login } = useAuth();
  useRedirectWhenLoggedIn();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validate(email, password);
    setFieldErrors(errors);
    setBanner(null);
    if (errors.email || errors.password) return;

    setSubmitting(true);
    try {
      await login(email.trim(), password);
      // useRedirectWhenLoggedIn moves on to ?next= or /home.
    } catch (error) {
      const emailError =
        error instanceof ApiError && error.code !== "email_password_mismatch"
          ? error.fieldErrors.email?.[0]
          : undefined;
      if (emailError) setFieldErrors({ email: emailError });
      else setBanner(bannerMessage(error));
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="mb-space-lg text-center">
        <h1 className="font-headline-md text-headline-md text-on-surface">Welcome back</h1>
        <p className="mt-space-xs font-body-md text-body-md text-outline">
          Enter your credentials to access your feed.
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
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={fieldErrors.email}
        />
        <PasswordField
          label="Password"
          name="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={fieldErrors.password}
        />
        <div className="pt-space-sm">
          <Button type="submit" block loading={submitting}>
            <span>Log in</span>
            <span aria-hidden="true" className="leading-none tracking-normal">
              →
            </span>
          </Button>
        </div>
      </form>

      <div className="mt-space-lg w-full rounded-lg bg-surface-container-low py-space-md text-center">
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="ml-0.5 font-medium text-secondary hover:underline">
            Sign up
          </Link>
        </p>
      </div>
    </>
  );
}
