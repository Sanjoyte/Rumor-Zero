"use client";

import Link from "next/link";
import { buttonClasses } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth/AuthProvider";

/**
 * The landing hero (Stitch a1, without its pill). Anonymous visitors get the sign-up buttons, which
 * is also what is prerendered; a signed-in visitor gets "Go to your feed" once the session is known.
 */
export function LandingHero() {
  const { status } = useAuth();
  const signedIn = status === "authenticated";
  return (
    <section className="mx-auto max-w-wide px-space-md pt-16 pb-14 text-center">
      <h1 className="mb-space-lg font-display-hero-mobile text-display-hero-mobile text-on-surface lg:font-display-hero lg:text-display-hero">
        A social platform where opinions are labelled, and facts are checked.
      </h1>
      <p className="mx-auto mb-space-xl max-w-2xl font-body-md text-body-md text-on-surface-variant sm:font-body-lg sm:text-body-lg">
        Every post is plain text and says up front whether it is an opinion or a fact. Opinions go
        straight up. Facts are checked, and you see the result next to the post.
      </p>
      <div className="flex flex-col items-center justify-center gap-space-md sm:flex-row">
        {signedIn ? (
          <Link href="/home" className={buttonClasses({ className: "w-full sm:w-auto" })}>
            Go to your feed
          </Link>
        ) : (
          <>
            <Link href="/signup" className={buttonClasses({ className: "w-full sm:w-auto" })}>
              Create account
            </Link>
            <Link
              href="/login"
              className={buttonClasses({ variant: "secondary", className: "w-full sm:w-auto" })}
            >
              I already have an account
            </Link>
          </>
        )}
      </div>
    </section>
  );
}
