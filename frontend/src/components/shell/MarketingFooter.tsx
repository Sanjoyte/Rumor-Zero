import Link from "next/link";
import { Logo } from "@/components/ui/Logo";

/** Only pages that exist (user decision, 2026-10-01). */
export const FOOTER_LINKS = [
  { label: "How verification works", href: "/how-it-works" },
  { label: "Privacy", href: "/privacy" },
  { label: "Terms", href: "/terms" },
] as const;

/**
 * The public footer (Stitch a1 L366–386): the logo, three links and "© 2026 Rumor Zero". No
 * tagline, fabricated company or edition label (ANALYSIS e).
 */
export function MarketingFooter() {
  return (
    <footer className="w-full border-t border-outline-variant/30 bg-surface-container-lowest py-space-xl font-body-sm text-body-sm text-outline">
      <div className="mx-auto max-w-wide px-space-lg">
        <div className="flex flex-col justify-between gap-space-md border-b border-outline-variant/30 pb-space-lg md:flex-row md:items-center">
          <Link href="/" className="self-start rounded-lg md:self-auto">
            <Logo size="sm" />
          </Link>
          <nav aria-label="Footer" className="flex flex-wrap items-center gap-space-lg">
            {FOOTER_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="transition-colors hover:text-on-surface"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex flex-col items-center justify-between gap-space-sm pt-space-lg font-label-badge text-label-badge font-normal text-outline sm:flex-row">
          <p>© 2026 Rumor Zero</p>
        </div>
      </div>
    </footer>
  );
}
