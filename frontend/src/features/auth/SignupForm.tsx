"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { PasswordField } from "@/components/ui/PasswordField";
import { PasswordStrengthMeter } from "@/components/ui/PasswordStrengthMeter";
import { TextField } from "@/components/ui/TextField";
import { ApiError } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/AuthProvider";
import { scorePassword } from "@/lib/password-strength";
import { bannerMessage } from "./messages";
import { Turnstile } from "./Turnstile";
import { useRedirectWhenLoggedIn } from "./useRedirectWhenLoggedIn";
import {
  USERNAME_FORMAT_MESSAGE,
  USERNAME_PATTERN,
  normalizeUsername,
  useUsernameAvailability,
} from "./useUsernameAvailability";

/** Django's MinimumLengthValidator; the other validators run on the server. */
export const MIN_PASSWORD_LENGTH = 8;

type Field = "email" | "username" | "password" | "turnstile_token";
type FieldErrors = Partial<Record<Field, string>>;
const FIELDS: Field[] = ["email", "username", "password", "turnstile_token"];

function validate(email: string, username: string, password: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!email.trim()) errors.email = "Enter your email address.";
  else if (!/^[^\s@]+@[^\s@]+$/.test(email.trim())) errors.email = "Enter a valid email address.";
  const handle = normalizeUsername(username);
  if (!handle) errors.username = "Choose a username.";
  else if (!USERNAME_PATTERN.test(handle)) errors.username = USERNAME_FORMAT_MESSAGE;
  if (password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  return errors;
}

export interface SignupFormProps {
  /** Defaults to NEXT_PUBLIC_TURNSTILE_SITE_KEY. Without one, sign-up is switched off. */
  siteKey?: string;
}

/**
 * `/signup` (Stitch a2, without its jargon: ANALYSIS b-5). The Turnstile widget replaces a2's
 * "Protected by Turnstile" callout, and the Google button waits for Part 3.
 */
export function SignupForm({ siteKey: siteKeyProp }: SignupFormProps) {
  const siteKey = siteKeyProp ?? process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
  const { signup } = useAuth();
  useRedirectWhenLoggedIn();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const availability = useUsernameAvailability(username);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validate(email, username, password);
    setFieldErrors(errors);
    setBanner(null);
    if (Object.keys(errors).length > 0 || !turnstileToken) return;

    setSubmitting(true);
    try {
      await signup({
        email: email.trim(),
        username: normalizeUsername(username),
        password,
        turnstileToken,
      });
      // useRedirectWhenLoggedIn moves on to /home, where the "Verify your email" banner shows.
    } catch (error) {
      const fromServer: FieldErrors = {};
      if (error instanceof ApiError) {
        for (const field of FIELDS) {
          const message = error.fieldErrors[field]?.[0];
          if (message) fromServer[field] = message;
        }
      }
      setFieldErrors(fromServer);
      if (Object.keys(fromServer).length === 0) setBanner(bannerMessage(error));
      // A Turnstile token works once, so every failed attempt needs a new one.
      setTurnstileToken(null);
      setResetKey((key) => key + 1);
      setSubmitting(false);
    }
  }

  const usernameError =
    fieldErrors.username ??
    (["taken", "reserved", "invalid"].includes(availability.status)
      ? (availability.message ?? undefined)
      : undefined);
  const usernameAvailable = !fieldErrors.username && availability.status === "available";

  return (
    <>
      <div className="mb-space-xl text-center">
        <h1 className="mb-space-sm font-headline-md text-headline-md text-on-surface">
          Create your account
        </h1>
        <p className="mx-auto max-w-xs font-body-md text-body-md text-outline">
          Join an editorial community committed to factual clarity.
        </p>
      </div>

      {!siteKey && (
        <Alert tone="info" className="mb-space-lg">
          Sign-up is unavailable right now.
        </Alert>
      )}
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
          error={fieldErrors.email}
        />
        <TextField
          label="Username"
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          value={username}
          onChange={(event) => {
            setUsername(event.target.value);
            setFieldErrors((current) => ({ ...current, username: undefined }));
          }}
          error={usernameError}
          success={usernameAvailable ? `Available: @${availability.username}` : undefined}
          hint={availability.status === "checking" ? "Checking…" : undefined}
          trailing={
            usernameAvailable ? (
              <span className="pointer-events-none text-primary">
                <Icon name="check" />
              </span>
            ) : undefined
          }
        />
        <div className="pt-0.5">
          <PasswordField
            label="Password"
            name="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={fieldErrors.password}
          />
          <PasswordStrengthMeter score={scorePassword(password)} />
        </div>
        {siteKey && (
          <div className="pt-space-xs">
            <Turnstile
              siteKey={siteKey}
              onToken={setTurnstileToken}
              resetKey={resetKey}
              error={fieldErrors.turnstile_token}
            />
          </div>
        )}
        <div className="pt-space-sm">
          <Button type="submit" block loading={submitting} disabled={!siteKey || !turnstileToken}>
            Create account
          </Button>
        </div>
        <p className="px-space-md pt-space-xs text-center font-body-sm text-body-sm text-outline">
          By creating an account, you agree to the{" "}
          <Link href="/terms" className="text-secondary hover:underline">
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="text-secondary hover:underline">
            Privacy Policy
          </Link>
          .
        </p>
        <div className="mt-space-md border-t border-outline-variant/30 pt-space-md">
          <p className="text-center font-body-sm text-body-sm text-on-surface-variant">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-secondary hover:underline">
              Log in
            </Link>
          </p>
        </div>
      </form>
    </>
  );
}
