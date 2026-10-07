"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { MouseEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button, buttonClasses } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/lib/auth/AuthProvider";
import { safeNextPath } from "@/lib/auth/next-path";
import { useResendVerification } from "./useResendVerification";

const LOGIN_TO_RESEND = `/login?next=${encodeURIComponent("/verify-email")}`;

/**
 * `/verify-email` (Stitch a4): "check your inbox". Sign-up lands here. It is never redirected
 * away: a verified user sees a short confirmation, an anonymous visitor a way back to log in.
 * Without Stitch's state switcher, "Simulate instant link click" and the "cryptographically
 * signed" jargon (ANALYSIS b-5).
 */
export function VerifyEmailPending() {
  const { status, user } = useAuth();

  if (status === "loading") return <PendingSkeleton />;
  if (status === "anonymous") return <AnonymousView />;
  if (user?.is_email_verified) return <VerifiedView />;
  return <PendingView email={user?.email ?? ""} />;
}

function PendingSkeleton() {
  return (
    <div aria-busy="true" className="space-y-space-md">
      <span className="sr-only">Loading…</span>
      <Skeleton className="mx-auto h-8 w-56" />
      <Skeleton className="mx-auto h-5 w-72" />
      <Skeleton className="h-11 w-full" />
    </div>
  );
}

function Heading({ children }: { children: string }) {
  return (
    <h1 className="mb-space-md text-center font-headline-md text-headline-md text-on-surface">
      {children}
    </h1>
  );
}

function PendingView({ email }: { email: string }) {
  const router = useRouter();
  const { secondsLeft, busy, status, resend } = useResendVerification({ cooldownOnMount: true });
  const waiting = secondsLeft > 0;

  function continueBrowsing(event: MouseEvent<HTMLAnchorElement>) {
    // `next` is read from the address now, so the page itself stays prerendered.
    event.preventDefault();
    const next = new URLSearchParams(window.location.search).get("next");
    router.push(safeNextPath(next) ?? "/home");
  }

  return (
    <div className="text-center">
      <Heading>Verify your email</Heading>
      <p className="mx-auto mb-space-lg max-w-sm font-body-md text-body-md text-on-surface-variant">
        We sent a verification link to{" "}
        <span className="font-semibold break-words text-on-surface">{email}</span>. Click the link
        to unlock posting.
      </p>

      <Alert tone="info" title="Read-only for now" className="mb-space-lg text-left">
        Verify your email to post, comment and report.
      </Alert>

      <div className="mb-space-md">
        {waiting ? (
          // a4's waiting state: secondary at 10% with secondary text. Button's variants can't be
          // tinted without fighting their own colour classes, so this one is spelled out.
          <button
            type="button"
            disabled
            className="inline-flex h-11 w-full cursor-not-allowed items-center justify-center gap-space-xs rounded-lg bg-secondary/10 px-space-md py-space-sm font-body-md text-body-md font-semibold text-secondary"
          >
            <Icon name="schedule" size="sm" />
            <span>Resend email ({secondsLeft}s)</span>
          </button>
        ) : (
          <Button block loading={busy} onClick={() => void resend()}>
            Resend email
          </Button>
        )}
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

      <p className="mx-auto mb-space-xl max-w-xs font-body-sm text-body-sm text-outline">
        Be sure to check your spam or junk folder if you don&apos;t see it in a few minutes.
      </p>

      <hr className="mb-space-lg border-t border-outline-variant/30" />
      <Link
        href="/home"
        onClick={continueBrowsing}
        className="inline-flex items-center font-body-md text-body-md font-medium text-secondary hover:text-on-secondary-container hover:underline"
      >
        Continue browsing read-only
        <span aria-hidden="true" className="ml-space-xs font-normal">
          →
        </span>
      </Link>
      <p className="mt-space-lg flex items-center justify-center gap-space-xs font-body-sm text-body-sm text-outline">
        <Icon name="lock" size="sm" />
        <span>Links expire 24 hours after they&apos;re sent.</span>
      </p>
    </div>
  );
}

function VerifiedView() {
  return (
    <div className="text-center">
      <Heading>Your email is verified</Heading>
      <p className="mx-auto mb-space-lg max-w-sm font-body-md text-body-md text-on-surface-variant">
        You can post, comment and report now.
      </p>
      <Link href="/home" className={buttonClasses({ block: true })}>
        <span>Start posting</span>
        <span aria-hidden="true">→</span>
      </Link>
    </div>
  );
}

function AnonymousView() {
  return (
    <div className="text-center">
      <Heading>Check your inbox</Heading>
      <p className="mx-auto mb-space-lg max-w-sm font-body-md text-body-md text-on-surface-variant">
        We sent a verification link to the address you signed up with. Click it to unlock posting.
      </p>
      <p className="mx-auto mb-space-lg max-w-xs font-body-sm text-body-sm text-outline">
        Be sure to check your spam or junk folder if you don&apos;t see it in a few minutes.
      </p>
      <Link href={LOGIN_TO_RESEND} className={buttonClasses({ variant: "secondary", block: true })}>
        Log in to resend
      </Link>
    </div>
  );
}
