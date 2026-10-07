"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonClasses } from "@/components/ui/Button";
import { PasswordField } from "@/components/ui/PasswordField";
import { PasswordStrengthMeter } from "@/components/ui/PasswordStrengthMeter";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { checkResetKey, resetPassword } from "@/lib/auth/auth-api";
import { useAuth } from "@/lib/auth/AuthProvider";
import { parseResetKey } from "@/lib/auth/email-key";
import { scorePassword } from "@/lib/password-strength";
import { bannerMessage, MESSAGES } from "./messages";
import { MIN_PASSWORD_LENGTH } from "./SignupForm";

type KeyState = "checking" | "valid" | "expired";

interface FieldErrors {
  password?: string;
  confirm?: string;
}

/**
 * `/reset-password/[key]` (Stitch a6). A skeleton while the key is checked (a dead link shows the
 * expired state before anyone types a password), then the form. Success logs the user in with the
 * token the reset returns. a6's "12 characters" is 8, the server's real minimum, and its audit-ID
 * and TLS footer is dropped (ANALYSIS b-5).
 */
export function ResetPasswordForm({ keyParam }: { keyParam: string }) {
  const { signInWithToken } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const key = parseResetKey(keyParam);
  const [keyState, setKeyState] = useState<KeyState>(key === null ? "expired" : "checking");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // One check per key, even when React StrictMode runs the effect twice.
  const checkedFor = useRef<string | null>(null);

  useEffect(() => {
    if (key === null || checkedFor.current === key) return;
    checkedFor.current = key;
    checkResetKey(key).then(
      () => setKeyState("valid"),
      (error: unknown) => {
        // Only a definite "no" is the expired state. If the check itself couldn't run (network,
        // a waking server), the form still works and the submit gives the real answer.
        setKeyState(error instanceof ApiError && error.status === 400 ? "expired" : "valid");
      },
    );
  }, [key]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (key === null) return;
    const errors: FieldErrors = {};
    if (password.length < MIN_PASSWORD_LENGTH) {
      errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
    } else if (confirm !== password) {
      errors.confirm = "The passwords don't match.";
    }
    setFieldErrors(errors);
    setBanner(null);
    if (errors.password || errors.confirm) return;

    setSubmitting(true);
    let token: string;
    try {
      token = await resetPassword(key, password);
    } catch (error) {
      if (error instanceof ApiError && error.status === 400) {
        if (error.fieldErrors.password?.length) {
          setFieldErrors({ password: error.fieldErrors.password[0] });
        } else if (error.fieldErrors.key?.length || error.code === "invalid_password_reset") {
          setKeyState("expired");
        } else {
          setBanner(bannerMessage(error));
        }
      } else {
        setBanner(bannerMessage(error));
      }
      setSubmitting(false);
      return;
    }
    try {
      await signInWithToken(token);
      toast.show(MESSAGES.passwordChanged, { tone: "success" });
      router.replace("/home");
    } catch {
      // The password did change (the key is used up); only loading the account failed.
      toast.show(MESSAGES.passwordChangedLogIn, { tone: "success" });
      router.replace("/login");
    }
  }

  if (keyState === "checking") return <Checking />;
  if (keyState === "expired") return <Expired />;

  return (
    <>
      <div className="mb-space-xl">
        <h1 className="mb-space-sm font-headline-md text-headline-md text-on-surface">
          Create new password
        </h1>
        <p className="font-body-md text-body-md text-outline">
          Choose a new password for your account. Use at least {MIN_PASSWORD_LENGTH} characters.
        </p>
      </div>

      {banner && (
        <Alert tone="error" onDismiss={() => setBanner(null)} className="mb-space-lg">
          <p className="font-medium">{banner}</p>
        </Alert>
      )}

      <form className="space-y-space-lg" noValidate onSubmit={onSubmit}>
        <div>
          <PasswordField
            label="New password"
            name="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={fieldErrors.password}
          />
          <PasswordStrengthMeter score={scorePassword(password)} />
        </div>
        <PasswordField
          label="Confirm new password"
          name="confirm"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          error={fieldErrors.confirm}
        />
        <Alert tone="info">This also signs you out on your other devices.</Alert>
        <Button type="submit" block loading={submitting}>
          <span>Reset password &amp; log in</span>
          <span aria-hidden="true" className="leading-none tracking-normal">
            →
          </span>
        </Button>
      </form>
    </>
  );
}

function Checking() {
  return (
    <div aria-busy="true" className="space-y-space-lg">
      <span className="sr-only">Checking your link…</span>
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-5 w-full" />
      <Skeleton className="h-11 w-full" />
      <Skeleton className="h-11 w-full" />
    </div>
  );
}

function Expired() {
  return (
    <div className="text-center">
      <h1 className="mb-space-md font-headline-md text-headline-md text-on-surface">
        This link has expired
      </h1>
      <Alert tone="error" className="mb-space-lg text-left">
        <p className="font-medium">
          Reset links work once and last 24 hours. This one is expired or already used.
        </p>
      </Alert>
      <Link href="/forgot-password" className={buttonClasses({ block: true })}>
        Request a new link
      </Link>
    </div>
  );
}
