import type { MetadataRoute } from "next";
import assets from "@/lib/brand-assets.json";

/** Web app manifest. Colours and icons come from the generated brand-assets.json (Part 0D). */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: assets.alt,
    short_name: assets.alt,
    description:
      "Text-only posts, labelled Opinion or Fact, with facts checked before you rely on them.",
    start_url: "/",
    display: "standalone",
    // The icons sit on the inverse-surface plate, so the install splash and toolbar use it too.
    theme_color: assets.plateColor,
    background_color: assets.plateColor,
    icons: assets.icons.map((icon) => ({
      src: icon.src,
      sizes: `${icon.width}x${icon.height}`,
      type: icon.type,
      purpose: icon.purpose as "any" | "maskable",
    })),
  };
}
