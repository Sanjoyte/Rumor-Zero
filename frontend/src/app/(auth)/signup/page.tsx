import type { Metadata } from "next";

export const metadata: Metadata = { title: "Sign up" };

/** Placeholder; Part 1 builds the form. */
export default function Page() {
  return (
    <div className="text-center">
      <h1 className="font-headline-md text-headline-md text-on-surface">Create your account</h1>
      <p className="mt-space-xs font-body-md text-body-md text-outline">Sign-up opens soon.</p>
    </div>
  );
}
