import { describe, expect, it } from "vitest";
import {
  FILTER_PARAMS,
  MAX_QUERY_LENGTH,
  parseSearchParams,
  SEARCH_FILTERS,
  searchHref,
} from "./search-params";

const parse = (query: string) => parseSearchParams(new URLSearchParams(query));

describe("parseSearchParams", () => {
  it("defaults to Posts and All with no query", () => {
    expect(parse("")).toEqual({ q: "", type: "posts", filter: "all" });
  });

  it("reads q, type and filter", () => {
    expect(parse("q=storm&type=users")).toEqual({ q: "storm", type: "users", filter: "all" });
    expect(parse("q=storm&filter=verified")).toEqual({
      q: "storm",
      type: "posts",
      filter: "verified",
    });
  });

  it("accepts each chip and nothing else", () => {
    for (const filter of SEARCH_FILTERS) expect(parse(`filter=${filter}`).filter).toBe(filter);
    for (const bad of ["fact", "VERIFIED", "removed", "", "x y", "__proto__"]) {
      expect(parse(`filter=${bad}`).filter).toBe("all");
    }
  });

  it("falls back to Posts for an unknown type", () => {
    for (const bad of ["people", "USERS", "", "post"])
      expect(parse(`type=${bad}`).type).toBe("posts");
  });

  it("has no chips on People", () => {
    expect(parse("type=users&filter=false").filter).toBe("all");
  });

  it("trims q and cuts it at the API's limit", () => {
    expect(parse("q=%20%20storm%20%20").q).toBe("storm");
    expect(parse(`q=${"x".repeat(300)}`).q).toHaveLength(MAX_QUERY_LENGTH);
    expect(parse("q=%20%20").q).toBe("");
  });

  it("reads the first value of a repeated key", () => {
    expect(parse("q=one&q=two&type=users&type=posts&filter=false&filter=review")).toEqual({
      q: "one",
      type: "users",
      filter: "all",
    });
  });

  it("decodes what the browser encoded", () => {
    expect(parse("q=a%26b%23c%2Bd+e").q).toBe("a&b#c+d e");
  });
});

describe("searchHref", () => {
  it("leaves out what is the default", () => {
    expect(searchHref({ q: "", type: "posts", filter: "all" })).toBe("/search");
    expect(searchHref({ q: "storm", type: "posts", filter: "all" })).toBe("/search?q=storm");
  });

  it("adds the tab or the chip", () => {
    expect(searchHref({ q: "storm", type: "users", filter: "all" })).toBe(
      "/search?q=storm&type=users",
    );
    expect(searchHref({ q: "storm", type: "posts", filter: "false" })).toBe(
      "/search?q=storm&filter=false",
    );
  });

  it("drops the chip on People", () => {
    expect(searchHref({ q: "", type: "users", filter: "false" })).toBe("/search?type=users");
  });

  it("encodes the query", () => {
    expect(searchHref({ q: "a&b #1", type: "posts", filter: "all" })).toBe("/search?q=a%26b+%231");
  });
});

describe("FILTER_PARAMS", () => {
  it("maps every chip to what the API takes", () => {
    expect(FILTER_PARAMS).toEqual({
      all: {},
      facts: { post_type: "fact" },
      opinions: { post_type: "opinion" },
      verified: { status: "verified_true" },
      false: { status: "verified_false" },
      review: { status: "under_review" },
    });
  });
});
