// @vitest-environment node
// Runs the real build into a scratch folder: read-only on design/, no output on an unsafe master,
// reproducible, and the committed text assets are not stale.
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { buildAll } from "./build-brand-assets.mjs";
import { BrandError } from "./svg.mjs";

const frontend = path.resolve(import.meta.dirname, "..", "..");
const repoRoot = path.dirname(frontend);
const masterPath = path.join(repoRoot, "design", "logo.svg");
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "rz-brand-"));
afterAll(() => fs.rmSync(scratch, { recursive: true, force: true }));

const sha = (file: string) =>
  crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const dirs = (name: string) => ({
  frontendDir: path.join(scratch, name, "frontend"),
  adminDir: path.join(scratch, name, "admin"),
});
const listFiles = (dir: string): string[] =>
  fs.existsSync(dir)
    ? fs
        .readdirSync(dir, { withFileTypes: true })
        .flatMap((e) =>
          e.isDirectory() ? listFiles(path.join(dir, e.name)) : [path.join(dir, e.name)],
        )
    : [];

describe("buildAll", () => {
  it("writes every ARCHITECTURE 14 asset and leaves design/ untouched", async () => {
    const before = [sha(masterPath), fs.statSync(masterPath).mtimeMs];
    const a = dirs("first");
    const result = await buildAll({
      masterPath,
      ...a,
      protectedDirs: [path.join(repoRoot, "design")],
    });

    const relative = result.written
      .map((f) => path.relative(path.join(scratch, "first"), f).split(path.sep).join("/"))
      .sort();
    expect(relative).toEqual(
      [
        "admin/logo-admin.png",
        "frontend/public/brand/email-logo.png",
        "frontend/public/brand/google-oauth-logo.png",
        "frontend/public/brand/icon-192.png",
        "frontend/public/brand/icon-512.png",
        "frontend/public/brand/icon-maskable-512.png",
        "frontend/public/brand/logo.svg",
        "frontend/public/brand/mark.svg",
        "frontend/src/app/apple-icon.png",
        "frontend/src/app/favicon.ico",
        "frontend/src/app/icon.svg",
        "frontend/src/app/opengraph-image.alt.txt",
        "frontend/src/app/opengraph-image.png",
        "frontend/src/app/twitter-image.alt.txt",
        "frontend/src/app/twitter-image.png",
        "frontend/src/lib/brand-assets.json",
      ].sort(),
    );
    expect([sha(masterPath), fs.statSync(masterPath).mtimeMs]).toEqual(before);
  });

  it("is reproducible: a second build gives identical bytes", async () => {
    const a = dirs("first");
    const b = dirs("second");
    await buildAll({ masterPath, ...b, protectedDirs: [path.join(repoRoot, "design")] });
    const names = (root: string) =>
      listFiles(root)
        .map((f) => path.relative(root, f))
        .sort();
    expect(names(path.join(scratch, "second"))).toEqual(names(path.join(scratch, "first")));
    for (const rel of names(path.join(scratch, "first"))) {
      expect(sha(path.join(scratch, "second", rel)), rel).toBe(
        sha(path.join(scratch, "first", rel)),
      );
    }
    expect(a.frontendDir).not.toBe(b.frontendDir);
  });

  it("matches the committed text assets (nothing is stale)", () => {
    const fresh = path.join(scratch, "first", "frontend");
    const committed = [
      "public/brand/logo.svg",
      "public/brand/mark.svg",
      "src/app/icon.svg",
      "src/app/opengraph-image.alt.txt",
      "src/app/twitter-image.alt.txt",
      "src/lib/brand-assets.json",
    ];
    for (const rel of committed) {
      expect(
        fs.readFileSync(path.join(frontend, rel), "utf8"),
        `${rel} is stale: run npm run brand:build`,
      ).toBe(fs.readFileSync(path.join(fresh, rel), "utf8"));
    }
  });

  it("refuses an unsafe master and writes nothing", async () => {
    const evil = path.join(scratch, "evil-input", "logo.svg");
    fs.mkdirSync(path.dirname(evil), { recursive: true });
    fs.writeFileSync(
      evil,
      fs
        .readFileSync(masterPath, "utf8")
        .replace("<defs>", "<script>alert(1)</script><text>x</text><defs>"),
    );
    const d = dirs("evil");
    await expect(buildAll({ masterPath: evil, ...d })).rejects.toThrow(BrandError);
    await expect(buildAll({ masterPath: evil, ...d })).rejects.toThrow(
      /<script> element[\s\S]*<text> element/,
    );
    expect(listFiles(path.join(scratch, "evil"))).toEqual([]);
  });

  it("fails when the mark selector no longer matches exactly one shape", async () => {
    const d = dirs("badselector");
    await expect(
      buildAll({
        masterPath,
        ...d,
        config: { ...(await import("./brand.config.json")).default, markSelector: "path.cls-2" },
      }),
    ).rejects.toThrow(/matched 4 <path> elements/);
    expect(listFiles(path.join(scratch, "badselector"))).toEqual([]);
  });

  it("refuses to write inside a protected folder", async () => {
    const d = dirs("protected");
    await expect(
      buildAll({
        masterPath,
        ...d,
        protectedDirs: [path.join(scratch, "protected", "frontend", "public")],
      }),
    ).rejects.toThrow(/Refusing to write/);
  });
});
