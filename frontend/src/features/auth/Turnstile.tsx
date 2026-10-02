"use client";

import { useEffect, useRef, useState } from "react";
import { ERROR_CLASSES } from "@/components/ui/field-styles";
import { Icon } from "@/components/ui/Icon";
import { loadTurnstile, type TurnstileApi } from "@/lib/turnstile";

export interface TurnstileProps {
  siteKey: string;
  /** Called with a new token, or null when it expires or fails. A token works once. */
  onToken: (token: string | null) => void;
  /** Changing it resets the widget (after every failed submit). */
  resetKey?: number;
  action?: string;
  error?: string;
}

/** Cloudflare's bot check on sign-up (explicit render; ARCHITECTURE §7). */
export function Turnstile({
  siteKey,
  onToken,
  resetKey = 0,
  action = "signup",
  error,
}: TurnstileProps) {
  const container = useRef<HTMLDivElement>(null);
  const api = useRef<TurnstileApi | null>(null);
  const widgetId = useRef<string | null>(null);
  const onTokenRef = useRef(onToken);
  const [loadFailed, setLoadFailed] = useState(false);

  useEffect(() => {
    onTokenRef.current = onToken;
  }, [onToken]);

  useEffect(() => {
    let cancelled = false;
    loadTurnstile().then(
      (turnstile) => {
        if (cancelled || !container.current) return;
        api.current = turnstile;
        widgetId.current = turnstile.render(container.current, {
          sitekey: siteKey,
          action,
          size: "flexible",
          callback: (token) => onTokenRef.current(token),
          "expired-callback": () => onTokenRef.current(null),
          "error-callback": () => onTokenRef.current(null),
        });
      },
      () => {
        if (!cancelled) setLoadFailed(true);
      },
    );
    return () => {
      cancelled = true;
      if (api.current && widgetId.current) api.current.remove(widgetId.current);
      widgetId.current = null;
    };
  }, [siteKey, action]);

  useEffect(() => {
    if (resetKey === 0 || !api.current || !widgetId.current) return;
    onTokenRef.current(null);
    api.current.reset(widgetId.current);
  }, [resetKey]);

  const message = loadFailed
    ? "The bot check couldn't load. Check your connection, then reload the page."
    : error;
  return (
    <div className="space-y-space-xs">
      {/* The flexible widget is 65px tall; reserving it keeps the button from jumping. */}
      <div ref={container} data-testid="turnstile" className="min-h-[65px]" />
      {message && (
        <p role="alert" className={ERROR_CLASSES}>
          <Icon name="error" size="sm" />
          {message}
        </p>
      )}
    </div>
  );
}
