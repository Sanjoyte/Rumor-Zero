import type { ReactNode } from "react";
import { MarketingFooter } from "@/components/shell/MarketingFooter";
import { MarketingNav } from "@/components/shell/MarketingNav";

/** Public pages: no app shell, prerendered (ARCHITECTURE §1). */
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col justify-between bg-surface">
      <MarketingNav />
      <main id="main" className="flex-grow">
        {children}
      </main>
      <MarketingFooter />
    </div>
  );
}
