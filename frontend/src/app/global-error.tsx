"use client";

import { AuthLayout } from "@/components/shell/AuthLayout";
import { Button } from "@/components/ui/Button";
import { fontVariables } from "./fonts";
import "./globals.css";

/** Replaces the root layout when it fails, so it brings its own <html>, fonts and styles. */
export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className={fontVariables}>
      <body>
        <AuthLayout>
          <div className="flex flex-col items-center gap-space-md text-center">
            <h1 className="font-headline-md text-headline-md text-on-surface">
              Something went wrong
            </h1>
            <p className="font-body-md text-body-md text-outline">
              Rumor Zero couldn&apos;t load. Try again in a moment.
            </p>
            <Button onClick={() => reset()}>Try again</Button>
          </div>
        </AuthLayout>
      </body>
    </html>
  );
}
