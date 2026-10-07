"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { ApiError } from "@/lib/api/client";
import { verifyEmail } from "@/lib/auth/auth-api";
import { useAuth } from "@/lib/auth/AuthProvider";
import { parseVerifyKey } from "@/lib/auth/email-key";
import { bannerMessage } from "./messages";
import { useResendVerification } from "./useResendVerification";

type Result = "verifying" | "verified" | "invalid" | "failed";

const LOGIN_TO_RESEND = `/login?next=${encodeURIComponent("/verify-email")}`;

/**
 * `/verify-email/[key]`: the page the email link opens. It always POSTs the key once, signed in
 * or not (a link never logs anyone in): verifying → verified, or the expired state with a way to
 * get a new link. The route parameter is decoded once (`parseVerifyKey`).
 */
export function VerifyEmailStatus({ keyParam }: { keyParam: string }) {
  const { status, user, reloadMe } = useAuth();
  const key = parseVerifyKey(keyParam);
  const [result, setResult] = useState<Result>(key === null ? "invalid" : "verifying");
  const [failure, setFailure] = useState<string | null>(null);
  // One request per key, even when React StrictMode runs the effect twice.
  const startedFor = useRef<string | null>(null);

  const run = useCallback(
    async (value: string) => {
      setResult("verifying");
      setFailure(null);
      try {
        await verifyEmail(value);
        setResult("verified");
        // The flag changed on the server: refresh this tab's user and, through the channel, the
        // other tabs'. A failure here is harmless; the next refresh catches up.
        await reloadMe().catch(() => {});
      } catch (error) {
        if (error instanceof ApiError && error.status === 400) {
          setResult("invalid");
        } else {
          setFailure(bannerMessage(error));
          setResult("failed");
        }
      }
    },
    [reloadMe],
  );

  useEffect(() => {
    if (key === null || status === "loading" || startedFor.current === key) return;
    startedFor.current = key;
    void run(key);
  }, [key, status, run]);

  if (result === "verifying") return <Verifying />;
  if (result === "verified") return <Verified signedIn={status === "authenticated"} />;
  if (result === "failed") {
    return <Failed message={failure ?? ""} onRetry={() => key !== null && void run(key)} />;
  }
  if (status === "authenticated" && user?.is_email_verified) {
    return <AlreadyVerified />;
  }
  return <Expired signedIn={status === "authenticated"} />;
}

function Heading({ children }: { children: string }) {
  return (
    <h1 className="mb-space-md text-center font-headline-md text-headline-md text-on-surface">
      {children}
    </h1>
  );
}

function Verifying() {
  return (
    <div aria-busy="true" className="space-y-space-md text-center">
      <Heading>Verifying…</Heading>
      <p className="font-body-md text-body-md text-on-surface-variant">
        Checking your verification link.
      </p>
      <Skeleton className="mx-auto h-11 w-full" />
    </div>
  );
}

function Verified({ signedIn }: { signedIn: boolean }) {
  return (
    <div className="text-center">
      <div className="mb-space-md flex justify-center text-primary">
        <Icon name="check_circle" size="2xl" filled />
      </div>
      <Heading>Your email is verified</Heading>
      <p className="mx-auto mb-space-lg max-w-sm font-body-md text-body-md text-on-surface-variant">
        You can post, comment and report now.
      </p>
      {signedIn ? (
        <Link href="/home" className={buttonClasses({ block: true })}>
          <span>Start posting</span>
          <span aria-hidden="true">→</span>
        </Link>
      ) : (
        <Link href="/login" className={buttonClasses({ block: true })}>
          <span>Log in to start posting</span>
          <span aria-hidden="true">→</span>
        </Link>
      )}
    </div>
  );
}

function AlreadyVerified() {
  return (
    <div className="text-center">
      <Heading>Your email is already verified</Heading>
      <p className="mx-auto mb-space-lg max-w-sm font-body-md text-body-md text-on-surface-variant">
        This link has been used. You&apos;re all set.
      </p>
      <Link href="/home" className={buttonClasses({ block: true })}>
        <span>Start posting</span>
        <span aria-hidden="true">→</span>
      </Link>
    </div>
  );
}

function Failed({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="text-center">
      <Heading>We couldn&apos;t verify your email</Heading>
      <Alert tone="error" className="mb-space-lg text-left">
        <p className="font-medium">{message}</p>
      </Alert>
      <Button block onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

function Expired({ signedIn }: { signedIn: boolean }) {
  return (
    <div className="text-center">
      <Heading>This link has expired</Heading>
      <p className="mx-auto mb-space-lg max-w-sm font-body-md text-body-md text-on-surface-variant">
        Verification links work once and last 24 hours. Send yourself a new one.
      </p>
      {signedIn ? (
        <InlineResend />
      ) : (
        <Link href={LOGIN_TO_RESEND} className={buttonClasses({ block: true })}>
          Log in to send a new link
        </Link>
      )}
    </div>
  );
}

function InlineResend() {
  const { secondsLeft, busy, status, resend } = useResendVerification();
  const waiting = secondsLeft > 0;
  return (
    <div>
      <Button block loading={busy} disabled={waiting} onClick={() => void resend()}>
        {waiting ? `Send a new link (${secondsLeft}s)` : "Send a new link"}
      </Button>
      <p
        role="status"
        aria-live="polite"
        className={
          status?.tone === "error"
            ? "mt-space-sm font-body-sm text-body-sm text-error"
            : "mt-space-sm font-body-sm text-body-sm text-on-surface-variant"
        }
      >
        {status?.message}
      </p>
    </div>
  );
}
