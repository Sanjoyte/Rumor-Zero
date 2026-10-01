import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import assets from "@/lib/brand-assets.json";
import manifest from "./manifest";

describe("web app manifest", () => {
  const result = manifest();

  it("is named Rumor Zero and starts at /", () => {
    expect(result.name).toBe("Rumor Zero");
    expect(result.short_name).toBe("Rumor Zero");
    expect(result.start_url).toBe("/");
  });

  it("takes its colours from the generated brand assets", () => {
    expect(result.theme_color).toBe(assets.plateColor);
    expect(result.background_color).toBe(assets.plateColor);
  });

  it("lists the 192, 512 and maskable 512 icons, all of which exist", () => {
    expect(result.icons?.map((i) => [i.sizes, i.purpose])).toEqual([
      ["192x192", "any"],
      ["512x512", "any"],
      ["512x512", "maskable"],
    ]);
    for (const icon of result.icons ?? []) {
      expect(icon.type).toBe("image/png");
      expect(fs.existsSync(path.join(process.cwd(), "public", icon.src.replace(/^\//, "")))).toBe(
        true,
      );
    }
  });
});
