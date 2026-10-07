/**
 * The keys in email links (ARCHITECTURE §7). A route parameter reaches the page percent-encoded
 * (Next 16 re-encodes every param, and allauth's verification key contains ":"), so it is decoded
 * once. Then only the characters a real key can contain are accepted: anything else is "invalid"
 * without a request, and a non-Latin-1 character can never reach a header (where `fetch` would
 * throw, which would read as "network error").
 */

/** allauth's verification key: `<base64>:<timestamp>:<signature>`. */
const VERIFY_KEY = /^[A-Za-z0-9_:-]{1,300}$/;
/** The reset key: `<uuid hex>-<timestamp>-<hash>`. */
const RESET_KEY = /^[0-9a-z-]{1,200}$/;

function decodeOnce(param: string): string | null {
  try {
    return decodeURIComponent(param);
  } catch {
    return null;
  }
}

/** The key to send to the API, or null when the link is malformed. */
export function parseVerifyKey(param: string): string | null {
  const key = decodeOnce(param);
  return key !== null && VERIFY_KEY.test(key) ? key : null;
}

/** The key to send to the API, or null when the link is malformed. */
export function parseResetKey(param: string): string | null {
  const key = decodeOnce(param);
  return key !== null && RESET_KEY.test(key) ? key : null;
}
