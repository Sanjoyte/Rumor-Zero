/**
 * Sources on a fact post: an http(s) URL or a DOI (ARCHITECTURE §4c).
 *
 * This is the client mirror of `backend/apps/posts/validators.py`, step for step, so the composer
 * and the server agree; both are driven by `backend/apps/posts/tests/source_vectors.json`. The
 * browser's `URL` parser is deliberately **not** the algorithm (it turns `\` into `/`, decodes `%xx`
 * in hosts and accepts `https:example.com`); it is used only to turn a non-ASCII host into
 * punycode. One thing the page can't do without a punycode library is check that an `xn--` label is
 * a real A-label: the server does, and its answer lands on that row. Nothing here is fetched.
 */
import type { PostSource, SourceKind } from "@/lib/api/types";
import { countCharacters } from "@/lib/format";

export const MAX_SOURCES = 5;
export const MAX_SOURCE_LENGTH = 500;
/** Raw input longer than this is refused before any work. */
const MAX_RAW_LENGTH = 2000;

const HELP_LINK =
  "Enter a link that starts with https:// or http://, or a DOI such as 10.1000/xyz.";
const HELP_DOI = "That doesn't look like a DOI. A DOI looks like 10.1000/xyz.";
const HELP_HOST = "Enter a full website address, such as example.org.";
const HELP_IP = "Links to IP addresses and localhost aren't allowed.";
const HELP_CREDENTIALS = "Links with a username or password aren't allowed.";
const HELP_CHARACTERS = "Links can't contain spaces, backslashes or hidden characters.";
const HELP_PORT = "That link's port number isn't valid.";
const HELP_EMPTY = "This source is empty.";
const HELP_TOO_LONG = `This source is too long (${MAX_SOURCE_LENGTH} characters at most).`;

// [0-9], not \d; anchored at both ends (JS `$` has no trailing-newline exception); no `i` flag.
const DOI_PATTERN = /^10\.[0-9]{4,9}\/[-._;()/:A-Za-z0-9]+$/;
// Without the `u` flag `i` folds ASCII only, so "httpſ://" doesn't read as https.
const DOI_PREFIX = /^(?:doi:[ \t]*|https?:\/\/(?:dx\.)?doi\.org\/)/i;
// RFC 3986 appendix B: the same split the server uses. `authority` is undefined without "//".
const URI_PATTERN = /^([A-Za-z][A-Za-z0-9+.-]*):(?:\/\/([^/?#]*))?([^?#]*)(\?[^#]*)?(#.*)?$/;
const LABEL_PATTERN = /^[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?$/;
const PORT_PATTERN = /^[0-9]{1,5}$/;
const NUMERIC_LABEL = /^(?:[0-9]+|0x[0-9a-f]*)$/;
// Cc control, Cf format (bidi marks), Cs surrogate, Zs/Zl/Zp spaces and separators, and "\".
// Built from a string: the project's TS target (ES2017) predates property escapes.
const FORBIDDEN = new RegExp("[\\\\\\p{Cc}\\p{Cf}\\p{Cs}\\p{Zs}\\p{Zl}\\p{Zp}]", "u");
const DEFAULT_PORTS: Record<string, number> = { http: 80, https: 443 };

export type SourceResult =
  { ok: true; value: string; kind: SourceKind } | { ok: false; message: string };

class Refused extends Error {}

/** `doi` for a stored bare DOI (it starts with `10.`), `url` otherwise. */
export function sourceKind(value: string): SourceKind {
  return value.startsWith("10.") ? "doi" : "url";
}

function trimAscii(value: string): string {
  return value.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, "");
}

function limited(value: string): string {
  if (countCharacters(value) > MAX_SOURCE_LENGTH) throw new Refused(HELP_TOO_LONG);
  return value;
}

/** The bare DOI when the input is one, null when it is an ordinary URL. */
function asDoi(value: string): string | null {
  const prefix = DOI_PREFIX.exec(value);
  if (prefix) {
    const rest = value.slice(prefix[0].length);
    if (DOI_PATTERN.test(rest)) return rest;
    if (prefix[0].toLowerCase().startsWith("doi:")) throw new Refused(HELP_DOI);
    return null; // a doi.org link that isn't a plain DOI (a query, say) is an ordinary URL
  }
  if (value.startsWith("10.")) {
    if (DOI_PATTERN.test(value)) return value;
    throw new Refused(HELP_DOI);
  }
  return null;
}

function punycode(host: string): string {
  try {
    return new URL(`http://${host}/`).hostname;
  } catch {
    throw new Refused(HELP_HOST);
  }
}

function normalizeHost(host: string): string {
  if (!host) throw new Refused("That link has no website address.");
  if (/[%[\]]/.test(host)) throw new Refused(host.includes("[") ? HELP_IP : HELP_HOST);
  const ascii = /^[\x00-\x7f]*$/.test(host);
  const name = ascii ? host.toLowerCase() : punycode(host);
  const labels = name.split(".");
  const last = labels[labels.length - 1];
  if (name === "localhost" || name.endsWith(".localhost") || NUMERIC_LABEL.test(last)) {
    throw new Refused(HELP_IP);
  }
  if (labels.length < 2 || name.length > 253 || !labels.every((l) => LABEL_PATTERN.test(l))) {
    throw new Refused(HELP_HOST);
  }
  return name;
}

function normalizeUrl(value: string): string {
  const match = URI_PATTERN.exec(value);
  const scheme = match?.[1].toLowerCase();
  if (!match || !scheme || !(scheme in DEFAULT_PORTS) || match[2] === undefined) {
    throw new Refused(HELP_LINK);
  }
  const authority = match[2];
  if (authority.includes("@")) throw new Refused(HELP_CREDENTIALS);
  const colon = authority.lastIndexOf(":");
  let hostPart = authority;
  let port: number | null = null;
  if (colon !== -1) {
    hostPart = authority.slice(0, colon);
    const digits = authority.slice(colon + 1);
    port = PORT_PATTERN.test(digits) ? parseInt(digits, 10) : 0;
    if (port < 1 || port > 65535) throw new Refused(HELP_PORT);
  }
  const host = normalizeHost(hostPart);
  const netloc = port !== null && port !== DEFAULT_PORTS[scheme] ? `${host}:${port}` : host;
  const rest = (match[3] || "/") + (match[4] ?? "") + (match[5] ?? "");
  // Only non-ASCII characters are percent-encoded (UTF-8, uppercase hex); the rest stays as typed.
  const encoded = Array.from(rest)
    .map((char) => (char.codePointAt(0)! > 127 ? encodeURIComponent(char) : char))
    .join("");
  return `${scheme}://${netloc}${encoded}`;
}

/** The stored form of one source, or a message for the row. */
export function normalizeSource(raw: string): SourceResult {
  try {
    const value = trimAscii(raw);
    if (!value) throw new Refused(HELP_EMPTY);
    if (countCharacters(value) > MAX_RAW_LENGTH) throw new Refused(HELP_TOO_LONG);
    const doi = asDoi(value);
    if (doi !== null) return { ok: true, value: limited(doi), kind: "doi" };
    if (FORBIDDEN.test(value)) throw new Refused(HELP_CHARACTERS);
    const url = limited(normalizeUrl(value));
    return { ok: true, value: url, kind: "url" };
  } catch (error) {
    if (error instanceof Refused) return { ok: false, message: error.message };
    throw error;
  }
}

export interface SourceRow {
  id: string;
  text: string;
}

export interface CheckedRows {
  /** The message to show under each row that has a problem, by row id. */
  errors: Record<string, string>;
  /** What to send: normalised, empty rows dropped, order kept. */
  sources: string[];
  /** The row id behind each entry of `sources` (a server error at `sources.N` belongs to row N). */
  rowIds: string[];
}

/** Check every row and flag repeats ("Same as source 1", by row number, like the server). */
export function checkSourceRows(rows: SourceRow[]): CheckedRows {
  const errors: Record<string, string> = {};
  const sources: string[] = [];
  const rowIds: string[] = [];
  const firstRow = new Map<string, number>();
  rows.forEach((row, index) => {
    if (!trimAscii(row.text)) return; // empty rows are dropped
    const result = normalizeSource(row.text);
    if (!result.ok) {
      errors[row.id] = result.message;
      return;
    }
    const key = result.kind === "doi" ? result.value.toLowerCase() : result.value;
    const first = firstRow.get(key);
    if (first !== undefined) {
      errors[row.id] = `Same as source ${first + 1}.`;
      return;
    }
    firstRow.set(key, index);
    sources.push(result.value);
    rowIds.push(row.id);
  });
  return { errors, sources, rowIds };
}

/** What a card shows for a source: a URL's host, or `doi.org/<doi>`. */
export function sourceLabel(source: PostSource): string {
  if (source.kind === "doi") return `doi.org/${source.value}`;
  try {
    return new URL(source.value).hostname || source.value;
  } catch {
    return source.value;
  }
}

/** Where a source links: a DOI to doi.org, a URL to itself. Anything not http(s) gets no link. */
export function sourceHref(source: PostSource): string | null {
  if (source.kind === "doi") return `https://doi.org/${source.value}`;
  return /^https?:\/\//i.test(source.value) ? source.value : null;
}
