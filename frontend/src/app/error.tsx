"use client";

import { AuthLayout } from "@/components/shell/AuthLayout";
import { Button } from "@/components/ui/Button";

/** Basic error page for a failed render (Part 15 polishes it). The error itself isn't shown. */
export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <AuthLayout>
      <div className="flex flex-col items-center gap-space-md text-center">
        <h1 className="font-headline-md text-headline-md text-on-surface">Something went wrong</h1>
        <p className="font-body-md text-body-md text-outline">
          The page couldn&apos;t be shown. Try again in a moment.
        </p>
        <Button onClick={() => reset()}>Try again</Button>
      </div>
    </AuthLayout>
  );
}
