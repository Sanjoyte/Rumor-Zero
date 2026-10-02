/**
 * Reads the claims of an access token without verifying it. The server verifies every token; the
 * browser only needs the user id (`sub`) and the lifetime (`exp - iat`) to schedule the refresh.
 */
export interface TokenClaims {
  sub: string;
  iat: number;
  exp: number;
}

function decodeSegment(segment: string): unknown {
  const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

/** `sub`, `iat` and `exp` of a JWT, or null when it isn't one. */
export function tokenClaims(token: string): TokenClaims | null {
  const parts = token.split(".");
  if (parts.length !== 3 || !parts[1]) return null;
  try {
    const payload = decodeSegment(parts[1]) as Record<string, unknown>;
    const { sub, iat, exp } = payload ?? {};
    if (typeof sub !== "string" || typeof iat !== "number" || typeof exp !== "number") return null;
    if (!(exp > iat)) return null;
    return { sub, iat, exp };
  } catch {
    return null;
  }
}

/** Seconds the token was issued for, measured on the server's clock. */
export function tokenLifetimeSeconds(claims: TokenClaims): number {
  return claims.exp - claims.iat;
}
