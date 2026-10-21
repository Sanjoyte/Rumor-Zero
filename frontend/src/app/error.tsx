"use client";

import Link from "next/link";
import { AuthLayout } from "@/components/shell/AuthLayout";
import { Button, buttonClasses } from "@/components/ui/Button";

/** Basic error page for a failed render (Part 15 added the home link). The error itself isn't shown. */
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
        <div className="flex flex-wrap justify-center gap-space-md">
          <Button onClick={() => reset()}>Try again</Button>
          <Link href="/" className={buttonClasses({ variant: "secondary" })}>
            Go to the home page
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
