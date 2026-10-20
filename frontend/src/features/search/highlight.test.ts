import { describe, expect, it } from "vitest";
import { lightStem, MAX_TERMS, queryTerms, splitByTerms } from "./highlight";

const marked = (text: string, terms: string[]) =>
  splitByTerms(text, terms)
    .filter((part) => part.match)
    .map((part) => part.text);

describe("lightStem", () => {
  it.each([
    ["running", "run"],
    ["runs", "run"],
    ["run", "run"],
    ["runner", "runner"],
    ["runway", "runwai"],
    ["storms", "storm"],
    ["warning", "warn"],
    ["stopped", "stop"],
    ["stopping", "stop"],
    ["stop", "stop"],
    ["hoped", "hop"],
    ["hoping", "hop"],
    ["hope", "hop"],
    ["stories", "stori"],
    ["story", "stori"],
    ["class", "class"],
    ["sing", "sing"],
    ["bed", "bed"],
    ["agreed", "agr"],
    ["agree", "agr"],
    ["Café", "café"],
    ["dog’s", "dog"],
  ])("%s -> %s", (word, stem) => {
    expect(lightStem(word)).toBe(stem);
  });

  it("gives the matching words one stem", () => {
    expect(new Set(["running", "runs", "run"].map(lightStem)).size).toBe(1);
    expect(lightStem("runner")).not.toBe(lightStem("run"));
    expect(lightStem("runway")).not.toBe(lightStem("run"));
  });
});

describe("queryTerms", () => {
  it("lower-cases words of two characters or more", () => {
    expect(queryTerms("Storm Warning x")).toEqual(["storm", "warning"]);
  });

  it("drops quotes but keeps the words of a phrase", () => {
    expect(queryTerms('"heavy rain" tonight')).toEqual(["heavy", "rain", "tonight"]);
  });

  it("ignores -word, -phrase and or, the tokens the server ignores", () => {
    expect(queryTerms("storm -flood or fire")).toEqual(["storm", "fire"]);
    expect(queryTerms('storm -"heavy rain"')).toEqual(["storm"]);
    expect(queryTerms("OR Or oR")).toEqual([]);
    expect(queryTerms("-only -negatives")).toEqual([]);
  });

  it("skips stop words and repeats", () => {
    expect(queryTerms("the storm and the storm of the year")).toEqual(["storm", "year"]);
  });

  it("keeps at most eight terms", () => {
    const terms = queryTerms("aa bb cc dd ee ff gg hh ii jj");
    expect(terms).toHaveLength(MAX_TERMS);
    expect(terms[MAX_TERMS - 1]).toBe("hh");
  });

  it("splits on punctuation and reads any script", () => {
    expect(queryTerms("rain,wind;snow")).toEqual(["rain", "wind", "snow"]);
    expect(queryTerms("日本語 привет")).toEqual(["日本語", "привет"]);
  });

  it("is empty for nothing", () => {
    expect(queryTerms("")).toEqual([]);
    expect(queryTerms("   ")).toEqual([]);
    expect(queryTerms("!!! ???")).toEqual([]);
  });
});

describe("splitByTerms", () => {
  it("returns the text whole when there is nothing to mark", () => {
    expect(splitByTerms("Some text", [])).toEqual([{ text: "Some text", match: false }]);
    expect(splitByTerms("", ["run"])).toEqual([{ text: "", match: false }]);
  });

  it("marks words that stem like a term, and only those", () => {
    expect(marked("I run, she runs and he was running", ["running"])).toEqual([
      "run",
      "runs",
      "running",
    ]);
    expect(marked("A runner on a runway", ["run"])).toEqual([]);
  });

  it("keeps the text intact when the parts are joined", () => {
    const text = "Rain, rain: go away -- come again!";
    expect(
      splitByTerms(text, ["rain"])
        .map((part) => part.text)
        .join(""),
    ).toBe(text);
  });

  it("marks case-insensitively and keeps the original case", () => {
    expect(marked("STORM Storm storm", ["storm"])).toEqual(["STORM", "Storm", "storm"]);
  });

  it("joins neighbouring text that isn't marked into one part", () => {
    expect(splitByTerms("one, two three", ["zzz"])).toEqual([
      { text: "one, two three", match: false },
    ]);
    expect(splitByTerms("a, b rain c, d", ["rain"])).toEqual([
      { text: "a, b ", match: false },
      { text: "rain", match: true },
      { text: " c, d", match: false },
    ]);
  });

  it("marks words next to each other separately", () => {
    expect(splitByTerms("rain rain", ["rain"])).toEqual([
      { text: "rain", match: true },
      { text: " ", match: false },
      { text: "rain", match: true },
    ]);
  });

  it("handles Unicode words and emoji", () => {
    expect(marked("Café opens 😀 café", ["café"])).toEqual(["Café", "café"]);
  });

  it("never treats the text or the query as HTML or a pattern", () => {
    const html = "<img src=x onerror=alert(1)> storm";
    expect(marked(html, ["storm"])).toEqual(["storm"]);
    expect(
      splitByTerms(html, ["storm"])
        .map((p) => p.text)
        .join(""),
    ).toBe(html);
    // Characters that would break a regular expression built from the query.
    expect(() => splitByTerms("a(b)[c]*+?", queryTerms("(((a[ *+? \\"))).not.toThrow();
    expect(marked("(a+b)", queryTerms("(a+b"))).toEqual([]);
  });
});
