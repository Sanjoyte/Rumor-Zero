import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

export interface UnverifiedBannerProps {
  /** Without it the banner has no Resend button (the shell stays presentational). */
  onResend?: () => void;
  /** Seconds until another email can be sent; the button waits while it is above 0. */
  secondsLeft?: number;
  busy?: boolean;
}

/**
 * Shown at the top of every app page while the email address isn't verified (ANALYSIS b-2):
 * unverified accounts are read-only. Part 2 adds the Resend action, with the same 60 s countdown
 * as `/verify-email`.
 */
export function UnverifiedBanner({ onResend, secondsLeft = 0, busy }: UnverifiedBannerProps) {
  const waiting = secondsLeft > 0;
  return (
    <div className="mx-auto w-full max-w-reading px-margin-mobile pt-space-lg md:px-space-lg">
      <Alert tone="warning" title="Verify your email to post, comment and report.">
        <p>Check your inbox for the link.</p>
        {onResend && (
          <div className="pt-space-sm">
            <Button variant="secondary" loading={busy} disabled={waiting} onClick={onResend}>
              {waiting ? `Resend link (${secondsLeft}s)` : "Resend link"}
            </Button>
          </div>
        )}
      </Alert>
    </div>
  );
}
