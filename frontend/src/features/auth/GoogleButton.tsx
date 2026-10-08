"use client";

import { useEffect, useRef, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Divider } from "@/components/ui/Divider";
import { useAuth } from "@/lib/auth/AuthProvider";
import { googleLogin } from "@/lib/auth/auth-api";
import {
  initializeGoogleIdentity,
  loadGoogleIdentity,
  releaseGoogleHandler,
} from "@/lib/google-identity";
import { MESSAGES, googleErrorMessage } from "./messages";

export interface GoogleButtonProps {
  /** The centred label of the rule under the button, such as "or continue with email". */
  dividerLabel: string;
  /** True while another sign-in (email and password) is in flight: a credential is ignored. */
  disabled?: boolean;
  /** Google's button was clicked: the form clears its last error. */
  onAttempt?: () => void;
  onError: (message: string) => void;
  /** Defaults to NEXT_PUBLIC_GOOGLE_CLIENT_ID. Without one nothing renders. */
  clientId?: string;
}

const MIN_WIDTH = 200;
const MAX_WIDTH = 400; // Google's own limit

type Status = "idle" | "signing-in" | "load-failed";

/**
 * "Continue with Google" for a2 and a3: Google's rendered button, then the "or" rule. It sends
 * the ID token to the API and signs in with the access token that comes back; the page's
 * `useRedirectWhenLoggedIn` then goes on to `?next=` or /home (a Google account is already
 * verified, so a sign-up doesn't go to /verify-email). Google gives its button no event for a
 * closed popup, so that is simply "nothing happened". Hidden when there is no client ID.
 */
export function GoogleButton({
  dividerLabel,
  disabled = false,
  onAttempt,
  onError,
  clientId: clientIdProp,
}: GoogleButtonProps) {
  const clientId = clientIdProp ?? process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";
  const { signInWithToken } = useAuth();
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status>("idle");
  const busy = useRef(false);
  // Google keeps the first callbacks it is given, so they read the latest props through a ref.
  const latest = useRef({ disabled, onAttempt, onError, signInWithToken });
  useEffect(() => {
    latest.current = { disabled, onAttempt, onError, signInWithToken };
  });

  useEffect(() => {
    const parent = container.current;
    if (!clientId || !parent) return;
    let cancelled = false;

    async function onCredential(credential: string) {
      const { disabled: off, onError: report, signInWithToken: signIn } = latest.current;
      if (busy.current || off) return;
      busy.current = true;
      setStatus("signing-in");
      try {
        await signIn(await googleLogin(credential, clientId));
        // useRedirectWhenLoggedIn takes it from here.
      } catch (error) {
        report(googleErrorMessage(error));
        busy.current = false;
        setStatus("idle");
      }
    }

    loadGoogleIdentity().then(
      (google) => {
        if (cancelled || !parent) return;
        initializeGoogleIdentity(google, clientId, onCredential);
        parent.replaceChildren(); // a changed client ID draws into the same container
        google.renderButton(parent, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "rectangular",
          logo_alignment: "center",
          locale: "en",
          width: Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, parent.clientWidth || MAX_WIDTH)),
          click_listener: () => latest.current.onAttempt?.(),
        });
      },
      () => {
        if (!cancelled) setStatus("load-failed");
      },
    );
    return () => {
      cancelled = true;
      releaseGoogleHandler(onCredential);
    };
  }, [clientId]);

  if (!clientId) return null;
  return (
    <>
      <div className="mb-space-lg">
        {/* Reserves the button's height so the form doesn't jump when Google's iframe arrives. */}
        <div ref={container} data-testid="google-button" className="flex min-h-10 justify-center" />
        {status === "signing-in" && (
          <p
            role="status"
            className="mt-space-sm text-center font-body-sm text-body-sm text-outline"
          >
            Signing in with Google…
          </p>
        )}
        {status === "load-failed" && (
          <Alert tone="error" className="mt-space-sm">
            {MESSAGES.googleUnavailable}
          </Alert>
        )}
      </div>
      <Divider label={dividerLabel} className="mb-space-lg" />
    </>
  );
}
