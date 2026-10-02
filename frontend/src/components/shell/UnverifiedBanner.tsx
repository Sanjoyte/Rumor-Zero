import { Alert } from "@/components/ui/Alert";

/**
 * Shown at the top of every app page while the email address isn't verified (ANALYSIS b-2):
 * unverified accounts are read-only. Part 2 adds the Resend action.
 */
export function UnverifiedBanner() {
  return (
    <div className="mx-auto w-full max-w-reading px-margin-mobile pt-space-lg md:px-space-lg">
      <Alert tone="warning" title="Verify your email to post, comment and report.">
        Check your inbox for the link.
      </Alert>
    </div>
  );
}
