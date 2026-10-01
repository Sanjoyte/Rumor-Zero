import Link from "next/link";
import { buttonClasses } from "@/components/ui/Button";

/** Placeholder landing page; Part 15 builds Stitch a1. */
export default function LandingPage() {
  return (
    <div className="mx-auto flex w-full max-w-wide flex-col items-start gap-space-lg px-space-lg py-space-xl">
      <h1 className="font-headline-lg text-headline-lg text-on-surface">
        Text-only posts, labelled Opinion or Fact.
      </h1>
      <p className="max-w-reading font-body-lg text-body-lg text-on-surface-variant">
        Opinions publish straight away. Facts are checked before you rely on them. The full landing
        page is coming soon.
      </p>
      <div className="flex flex-wrap gap-space-md">
        <Link href="/home" className={buttonClasses()}>
          Browse posts
        </Link>
        <Link href="/how-it-works" className={buttonClasses({ variant: "secondary" })}>
          How verification works
        </Link>
      </div>
    </div>
  );
}
