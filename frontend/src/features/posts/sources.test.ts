import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  MAX_SOURCES,
  checkSourceRows,
  normalizeSource,
  sourceHref,
  sourceKind,
  sourceLabel,
} from "./sources";

// The same vectors the backend's `test_validators.py` runs, so the page and the server can't drift.
const VECTORS = JSON.parse(
  fs.readFileSync(
    path.resolve(import.meta.dirname, "../../../../backend/apps/posts/tests/source_vectors.json"),
    "utf8",
  ),
) as {
  accept: { input: string; value: string; kind: "url" | "doi" }[];
  reject: string[];
  server_only_reject: string[];
  lists: {
    inputs: string[];
    ok?: string[];
    bad?: Record<string, string>;
    too_many?: boolean;
  }[];
};

describe("normalizeSource: the shared vectors", () => {
  it.each(VECTORS.accept.map((c) => [JSON.stringify(c.input).slice(0, 70), c] as const))(
    "accepts %s",
    (_name, c) => {
      expect(normalizeSource(c.input)).toEqual({ ok: true, value: c.value, kind: c.kind });
    },
  );

  it.each(VECTORS.reject.map((input) => [JSON.stringify(input).slice(0, 70), input] as const))(
    "rejects %s",
    (_name, input) => {
      const result = normalizeSource(input);
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.message.length).toBeGreaterThan(0);
    },
  );

  it.each(VECTORS.accept.map((c) => [JSON.stringify(c.input).slice(0, 70), c] as const))(
    "normalising %s twice changes nothing",
    (_name, c) => {
      expect(normalizeSource(c.value)).toEqual({ ok: true, value: c.value, kind: c.kind });
    },
  );

  it("leaves fake punycode labels to the server (the browser accepts them as they are)", () => {
    // Listed in the vectors as server-only rejections: the page can't tell without a punycode
    // library, and the server's 400 lands on the row.
    for (const input of VECTORS.server_only_reject) {
      expect(normalizeSource(input).ok).toBe(true);
    }
  });
});

describe("normalizeSource: messages", () => {
  const message = (input: string) => {
    const result = normalizeSource(input);
    return result.ok ? null : result.message;
  };

  it("says what to do for each kind of mistake", () => {
    expect(message("javascript:alert(1)")).toContain("starts with https://");
    expect(message("example.org")).toContain("starts with https://");
    expect(message("doi:abc")).toContain("doesn't look like a DOI");
    expect(message("10.12/x")).toContain("doesn't look like a DOI");
    expect(message("https://user:pw@example.org/")).toContain("username or password");
    expect(message("http://127.0.0.1/")).toContain("IP addresses and localhost");
    expect(message("https://localhost/")).toContain("IP addresses and localhost");
    expect(message("https://intranet/")).toContain("full website address");
    expect(message("https://example.org/a b")).toContain("spaces, backslashes");
    expect(message("https://example.org:99999/")).toContain("port number");
    expect(message("")).toContain("empty");
    expect(message("https://example.org/" + "a".repeat(600))).toContain("too long");
  });

  it("refuses what the browser's own parser would quietly repair", () => {
    expect(new URL("https://good.com\\evil.com/").hostname).toBe("good.com"); // the trap
    expect(normalizeSource("https://good.com\\evil.com/").ok).toBe(false);
    expect(new URL("https://exa%6dple.com/").hostname).toBe("example.com");
    expect(normalizeSource("https://exa%6dple.com/").ok).toBe(false);
    expect(new URL("https:example.com").hostname).toBe("example.com");
    expect(normalizeSource("https:example.com").ok).toBe(false);
  });

  it("applies the length limit after punycode and percent-encoding", () => {
    expect(normalizeSource("https://example.org/" + "€".repeat(150)).ok).toBe(false);
    const base = "https://example.org/";
    expect(normalizeSource(base + "a".repeat(500 - base.length)).ok).toBe(true);
    expect(normalizeSource(base + "a".repeat(501 - base.length)).ok).toBe(false);
  });
});

describe("sourceKind", () => {
  it("tells a stored DOI from a stored URL", () => {
    expect(sourceKind("10.1000/xyz")).toBe("doi");
    expect(sourceKind("https://example.org/")).toBe("url");
  });
});

describe("checkSourceRows", () => {
  const rows = (...texts: string[]) => texts.map((text, i) => ({ id: `r${i}`, text }));

  it("drops empty rows and keeps the order", () => {
    const checked = checkSourceRows(rows("https://b.example/", "", "doi:10.1000/a", "   "));
    expect(checked.sources).toEqual(["https://b.example/", "10.1000/a"]);
    expect(checked.rowIds).toEqual(["r0", "r2"]);
    expect(checked.errors).toEqual({});
  });

  it("flags a repeat on the later row, with the earlier row's number", () => {
    const checked = checkSourceRows(
      rows("doi:10.1000/xyz", "https://a.example/", "https://doi.org/10.1000/XYZ"),
    );
    expect(checked.errors).toEqual({ r2: "Same as source 1." });
    expect(checked.sources).toEqual(["10.1000/xyz", "https://a.example/"]);
  });

  it("treats URLs that differ only in the path's case as different, as the server does", () => {
    const checked = checkSourceRows(rows("https://example.org/A", "https://example.org/a"));
    expect(checked.errors).toEqual({});
  });

  it("reports every bad row at once", () => {
    const checked = checkSourceRows(
      rows("javascript:x", "https://a.example/", "http://127.0.0.1/"),
    );
    expect(Object.keys(checked.errors)).toEqual(["r0", "r2"]);
    expect(checked.sources).toEqual(["https://a.example/"]);
  });

  it("maps the sent index back to its row when an empty row came first", () => {
    const checked = checkSourceRows(rows("", "https://a.example/", "10.1000/b"));
    // Server error `sources.1` is the second thing sent: row r2.
    expect(checked.rowIds[1]).toBe("r2");
  });

  it.each(VECTORS.lists.filter((c) => !c.too_many).map((c) => [c.inputs.length, c] as const))(
    "agrees with the shared list vectors (%i inputs)",
    (_count, c) => {
      const checked = checkSourceRows(c.inputs.map((text, i) => ({ id: String(i), text })));
      if (c.ok) {
        expect(checked.errors).toEqual({});
        expect(checked.sources).toEqual(c.ok);
        return;
      }
      expect(Object.keys(checked.errors).sort()).toEqual(Object.keys(c.bad ?? {}).sort());
      for (const [index, expected] of Object.entries(c.bad ?? {})) {
        if (expected !== "invalid") expect(checked.errors[index]).toBe(expected);
      }
    },
  );

  it("knows the limit the composer enforces", () => {
    expect(MAX_SOURCES).toBe(5);
  });
});

describe("sourceLabel and sourceHref", () => {
  it("shows a URL's host and a DOI as doi.org/…", () => {
    expect(sourceLabel({ value: "https://www.iea.org/reports/x?y=1", kind: "url" })).toBe(
      "www.iea.org",
    );
    expect(sourceLabel({ value: "https://xn--bcher-kva.example/", kind: "url" })).toBe(
      "xn--bcher-kva.example",
    );
    expect(sourceLabel({ value: "10.1038/s41558-024-02102", kind: "doi" })).toBe(
      "doi.org/10.1038/s41558-024-02102",
    );
  });

  it("falls back to the raw value when there is no host to show", () => {
    expect(sourceLabel({ value: "javascript:alert(1)", kind: "url" })).toBe("javascript:alert(1)");
    expect(sourceLabel({ value: "not a url", kind: "url" })).toBe("not a url");
  });

  it("links a DOI to doi.org and a URL to itself", () => {
    expect(sourceHref({ value: "10.1000/xyz", kind: "doi" })).toBe("https://doi.org/10.1000/xyz");
    expect(sourceHref({ value: "https://example.org/a", kind: "url" })).toBe(
      "https://example.org/a",
    );
  });

  it("never links anything that isn't http(s)", () => {
    expect(sourceHref({ value: "javascript:alert(1)", kind: "url" })).toBeNull();
    expect(sourceHref({ value: "data:text/html,hi", kind: "url" })).toBeNull();
  });
});
