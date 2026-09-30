import { describe, expect, it } from "vitest";
import { cn } from "./cn";

describe("cn", () => {
  it("joins strings and skips falsy values", () => {
    expect(cn("a", false, null, undefined, "", "b")).toBe("a b");
  });

  it("flattens nested arrays and keeps conditional classes", () => {
    const active = true;
    expect(cn("a", [active && "b", ["c", false]], "d")).toBe("a b c d");
  });

  it("returns an empty string when nothing is left", () => {
    expect(cn(false, null)).toBe("");
  });
});
