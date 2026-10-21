import { FeatureCards } from "@/features/landing/FeatureCards";
import { LandingHero } from "@/features/landing/LandingHero";
import { RecentPreview } from "@/features/landing/RecentPreview";

/** `/` (Part 15, Stitch a1): prerendered; only the preview and the signed-in button run in the browser. */
export default function LandingPage() {
  return (
    <>
      <LandingHero />
      <FeatureCards />
      <RecentPreview />
    </>
  );
}
