/**
 * Marking the search terms in a result (Part 12), client-side and without HTML: the text is split
 * into word and non-word runs and each run is either plain or a match, so nothing is parsed or
 * injected. No regular expression is built from the query either, so there is no backtracking and
 * no escaping to get wrong.
 *
 * It is approximate by design: Postgres stems with Snowball, this with the few rules that matter
 * (`lightStem`), so a result can match without a mark and a mark never appears on a word the
 * server wouldn't match ("runner" and "runway" stay unmarked for "run").
 */

export const MAX_TERMS = 8;

/** Words Postgres's English configuration ignores, plus a few it would too. */
const STOP_WORDS = new Set(
  (
    "a an and are as at be but by do for from had has have he her his how i if in into is it " +
    "its me my no not of on or our she so than that the their them then there these they this " +
    "to too was we were what when which who will with you your"
  ).split(" "),
);

/** One token of a websearch query: `-"a phrase"`, `"a phrase"`, `-word` or `word`. */
const TOKEN = /-?"[^"]*"?|\S+/g;
const WORDS = /[\p{L}\p{N}]+/gu;
const RUNS = /[\p{L}\p{N}]+|[^\p{L}\p{N}]+/gu;
const DOUBLED = new Set(["bb", "dd", "ff", "gg", "mm", "nn", "pp", "rr", "tt"]);

/**
 * The few Snowball rules that decide whether two English words match: `'s`, `ing`/`ed` (with at
 * least three letters left, then an undoubled consonant), a plural `s`, a final `y` → `i` (so
 * `stories` and `story` agree) and a final `e` (or `ee`). So `running`, `runs` and `run` share
 * `run`.
 */
export function lightStem(word: string): string {
  let stem = word.toLowerCase().replace(/['’]s$/, "");
  if (
    (stem.endsWith("ing") && stem.length - 3 >= 3) ||
    (stem.endsWith("ed") && stem.length - 2 >= 3)
  ) {
    stem = stem.slice(0, stem.endsWith("ing") ? -3 : -2);
    if (DOUBLED.has(stem.slice(-2))) stem = stem.slice(0, -1);
  } else if (stem.length > 3 && stem.endsWith("s") && !stem.endsWith("ss")) {
    stem = stem.slice(0, -1);
  }
  if (stem.length > 2 && stem.endsWith("y")) stem = `${stem.slice(0, -1)}i`;
  // One or two (`agree`, `agreed` -> `agre`): both forms must end alike.
  if (stem.length > 3) stem = stem.replace(/e{1,2}$/, "");
  return stem;
}

/**
 * The words of a websearch query worth marking: quotes dropped, `-word` and `or` ignored (the same
 * tokens the server ignores), words of two characters or more, lower-cased, no stop words, no
 * repeats, at most eight.
 */
export function queryTerms(query: string): string[] {
  const terms: string[] = [];
  for (const token of query.match(TOKEN) ?? []) {
    if (token.toLowerCase() === "or" || token.startsWith("-")) continue;
    for (const word of token.match(WORDS) ?? []) {
      const term = word.toLowerCase();
      if (term.length < 2 || STOP_WORDS.has(term) || terms.includes(term)) continue;
      terms.push(term);
      if (terms.length === MAX_TERMS) return terms;
    }
  }
  return terms;
}

export interface TextPart {
  text: string;
  match: boolean;
}

/** `text` cut into consecutive parts, the words that stem like one of `terms` marked `match`. */
export function splitByTerms(text: string, terms: readonly string[]): TextPart[] {
  if (terms.length === 0 || text === "") return [{ text, match: false }];
  const stems = new Set(terms.map(lightStem));
  const parts: TextPart[] = [];
  for (const run of text.match(RUNS) ?? []) {
    const match = stems.has(lightStem(run));
    const last = parts[parts.length - 1];
    if (last && last.match === match) last.text += run;
    else parts.push({ text: run, match });
  }
  return parts;
}
