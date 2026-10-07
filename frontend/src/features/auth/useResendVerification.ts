"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";
import { resendVerificationEmail } from "@/lib/auth/auth-api";
import { useAuth } from "@/lib/auth/AuthProvider";
import { bannerMessage, MESSAGES } from "./messages";

/** The server allows one verification email per 60 s per address (ARCHITECTURE §3). */
export const RESEND_COOLDOWN_SECONDS = 60;

export interface ResendStatus {
  tone: "success" | "info" | "error";
  message: string;
}

export interface UseResendVerificationOptions {
  /** Start the countdown on mount: the sign-up email has just been sent. */
  cooldownOnMount?: boolean;
  /** Told about every outcome, e.g. to show a toast. */
  onResult?: (status: ResendStatus) => void;
}

export interface ResendVerification {
  /** Seconds until the next send is allowed; 0 when it is allowed now. */
  secondsLeft: number;
  busy: boolean;
  /** The latest outcome, for an `aria-live` line. */
  status: ResendStatus | null;
  resend: () => Promise<void>;
}

/**
 * Resend the verification email, with the 60 s countdown (Stitch a4). The countdown is measured
 * against a deadline, so a throttled background tab doesn't slow it down. A 429 (we don't know
 * whether the minute or the daily bucket is full) restarts it, and a 409 means the address got
 * verified elsewhere, so `/me` is reloaded and the banner goes away.
 */
export function useResendVerification({
  cooldownOnMount = false,
  onResult,
}: UseResendVerificationOptions = {}): ResendVerification {
  const { reloadMe } = useAuth();
  const [secondsLeft, setSecondsLeft] = useState(cooldownOnMount ? RESEND_COOLDOWN_SECONDS : 0);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<ResendStatus | null>(null);
  const deadline = useRef<number | null>(null);
  const sending = useRef(false);
  const onResultRef = useRef(onResult);
  useEffect(() => {
    onResultRef.current = onResult;
  });

  // Declared before the tick effect, so the deadline exists when the first tick reads it.
  useEffect(() => {
    if (cooldownOnMount) deadline.current = Date.now() + RESEND_COOLDOWN_SECONDS * 1000;
  }, [cooldownOnMount]);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const timer = setTimeout(() => {
      const remaining = deadline.current === null ? 0 : deadline.current - Date.now();
      setSecondsLeft(Math.max(0, Math.ceil(remaining / 1000)));
    }, 1000);
    return () => clearTimeout(timer);
  }, [secondsLeft]);

  const startCooldown = useCallback(() => {
    deadline.current = Date.now() + RESEND_COOLDOWN_SECONDS * 1000;
    setSecondsLeft(RESEND_COOLDOWN_SECONDS);
  }, []);

  const resend = useCallback(async () => {
    if (sending.current || secondsLeft > 0) return;
    sending.current = true;
    setBusy(true);
    let outcome: ResendStatus;
    try {
      await resendVerificationEmail();
      startCooldown();
      outcome = { tone: "success", message: MESSAGES.resendSent };
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        startCooldown();
        outcome = { tone: "info", message: MESSAGES.resendThrottled };
      } else if (error instanceof ApiError && error.code === "already_verified") {
        await reloadMe().catch(() => {});
        outcome = { tone: "success", message: MESSAGES.alreadyVerified };
      } else {
        outcome = { tone: "error", message: bannerMessage(error) };
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
    setStatus(outcome);
    onResultRef.current?.(outcome);
  }, [secondsLeft, reloadMe, startCooldown]);

  return { secondsLeft, busy, status, resend };
}
