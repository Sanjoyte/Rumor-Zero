import { describe, expect, it } from "vitest";
import { parseResetKey, parseVerifyKey } from "./email-key";

describe("parseVerifyKey", () => {
  it("decodes the route parameter once", () => {
    // allauth's key has two ":"; the route param arrives percent-encoded.
    expect(parseVerifyKey("Mg%3A1vABcd%3Aabc-DEF_123")).toBe("Mg:1vABcd:abc-DEF_123");
    expect(parseVerifyKey("Mg:1vABcd:abc-DEF_123")).toBe("Mg:1vABcd:abc-DEF_123");
  });

  it("never decodes twice", () => {
    // "%253A" is a literal "%3A" after one decode: not a key character, so it's refused.
    expect(parseVerifyKey("Mg%253A1v")).toBeNull();
  });

  it.each([
    "",
    "%",
    "%E0%A4%A",
    "a b",
    "a%20b",
    "a/b",
    "a%2Fb",
    "a.b",
    "ünï",
    "%C3%BC",
    "key\n",
    "a".repeat(301),
  ])("refuses %j", (param) => {
    expect(parseVerifyKey(param)).toBeNull();
  });

  it("accepts the longest allowed key", () => {
    expect(parseVerifyKey("a".repeat(300))).toBe("a".repeat(300));
  });
});

describe("parseResetKey", () => {
  const key = "0123456789abcdef0123456789abcdef-1abc-0fed1234";

  it("accepts a real-looking reset key", () => {
    expect(parseResetKey(key)).toBe(key);
  });

  it("decodes once", () => {
    expect(parseResetKey("0123abcd%2D1abc%2D0fed")).toBe("0123abcd-1abc-0fed");
  });

  it.each(["", "%", "ABC-1-2", "a:b", "a b", "a_b", "a/b", "ünï", "a".repeat(201), "%C3%BC"])(
    "refuses %j",
    (param) => {
      expect(parseResetKey(param)).toBeNull();
    },
  );

  it("accepts the longest allowed key", () => {
    expect(parseResetKey("a".repeat(200))).toBe("a".repeat(200));
  });
});
