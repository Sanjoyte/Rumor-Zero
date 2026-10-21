import type { Metadata } from "next";
import Link from "next/link";
import { AuthLayout } from "@/components/shell/AuthLayout";
import { buttonClasses } from "@/components/ui/Button";

export const metadata: Metadata = { title: "Page not found" };

/** Basic 404 (ARCHITECTURE §14 places the logo here in 0C; Part 15 added the second link). */
export default function NotFound() {
  return (
    <AuthLayout>
      <div className="flex flex-col items-center gap-space-md text-center">
        <h1 className="font-headline-md text-headline-md text-on-surface">Page not found</h1>
        <p className="font-body-md text-body-md text-outline">
          This page doesn&apos;t exist, or it has moved.
        </p>
        <div className="flex flex-wrap justify-center gap-space-md">
          <Link href="/" className={buttonClasses()}>
            Go to the home page
          </Link>
          <Link href="/home" className={buttonClasses({ variant: "secondary" })}>
            Browse posts
          </Link>
        </div>
      </div>
    </AuthLayout>
  );
}
