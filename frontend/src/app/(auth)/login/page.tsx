import type { Metadata } from "next";

export const metadata: Metadata = { title: "Log in" };

/** Placeholder; Part 1 builds the form. */
export default function Page() {
  return (
    <div className="text-center">
      <h1 className="font-headline-md text-headline-md text-on-surface">Welcome back</h1>
      <p className="mt-space-xs font-body-md text-body-md text-outline">Logging in opens soon.</p>
    </div>
  );
}
