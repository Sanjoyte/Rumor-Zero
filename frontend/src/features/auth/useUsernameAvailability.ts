"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api/client";
import { AUTH_PATHS } from "@/lib/auth/auth-api";

/** The rule in ARCHITECTURE §2, checked here first so a bad format costs no request. */
export const USERNAME_PATTERN = /^[a-z0-9_]{3,30}$/;
export const USERNAME_FORMAT_MESSAGE =
  "Usernames are 3–30 characters: lowercase letters, numbers and underscores only.";
export const DEBOUNCE_MS = 400;

export type UsernameStatus = "idle" | "checking" | "available" | "taken" | "reserved" | "invalid";

export interface UsernameAvailability {
  status: UsernameStatus;
  /** The username as it will be stored (NFKC, trimmed, lowercase). */
  username: string;
  message: string | null;
}

interface AvailabilityResponse {
  username: string;
  available: boolean;
  reason: null | "invalid" | "reserved" | "taken";
  message: string;
}

export function normalizeUsername(value: string): string {
  return value.normalize("NFKC").trim().toLowerCase();
}

const IDLE: UsernameAvailability = { status: "idle", username: "", message: null };

/**
 * Live check for the sign-up form: waits 400 ms after the last keystroke, aborts stale requests,
 * and shows nothing on a 429 or a network error (the server decides at submit).
 */
export function useUsernameAvailability(value: string): UsernameAvailability {
  const username = normalizeUsername(value);
  const [result, setResult] = useState<UsernameAvailability>(IDLE);

  const formatOk = USERNAME_PATTERN.test(username);
  useEffect(() => {
    if (!username || !formatOk) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setResult({ status: "checking", username, message: null });
      api
        .get<AvailabilityResponse>(
          `${AUTH_PATHS.usernameAvailable}?u=${encodeURIComponent(username)}`,
          { signal: controller.signal, token: false },
        )
        .then((answer) => {
          if (controller.signal.aborted) return;
          setResult({
            status: answer.available ? "available" : (answer.reason ?? "invalid"),
            username: answer.username,
            message: answer.available ? null : answer.message,
          });
        })
        .catch(() => {
          if (!controller.signal.aborted) setResult(IDLE);
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [username, formatOk]);

  if (!username) return IDLE;
  if (!formatOk) return { status: "invalid", username, message: USERNAME_FORMAT_MESSAGE };
  // While the debounce runs there is no answer yet (and never a stale one for another name).
  if (result.username !== username) return { status: "idle", username, message: null };
  return result;
}
