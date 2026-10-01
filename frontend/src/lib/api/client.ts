/**
 * The only way the browser calls the API (ARCHITECTURE §10). Every call goes to the relative
 * "/api" base on the frontend origin, never to BACKEND_ORIGIN.
 *
 * Errors from DRF, allauth, the relay and the network all become one `ApiError` shape. Part 1 wires
 * token refresh into the 401 hook.
 */
import type { AllauthBody } from "./types";

/** Call types, so a later "direct to Render" escape hatch is an env change (ANALYSIS d). */
export type ApiKind = "app" | "auth";

/** Always the relay for now. Only refresh and logout would have to stay on it. */
export function baseFor(kind: ApiKind): string {
  void kind;
  return "/api";
}

export type FieldErrors = Record<string, string[]>;

export interface ApiErrorInit {
  status: number;
  code: string;
  detail: string;
  fieldErrors?: FieldErrors;
  retryAfter?: number | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly fieldErrors: FieldErrors;
  /** Seconds to wait, from a 429/503 `Retry-After`. */
  readonly retryAfter: number | null;

  constructor({ status, code, detail, fieldErrors = {}, retryAfter = null }: ApiErrorInit) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.fieldErrors = fieldErrors;
    this.retryAfter = retryAfter;
  }
}

const DEFAULT_CODES: Record<number, string> = {
  0: "network_error",
  400: "invalid",
  401: "not_authenticated",
  403: "permission_denied",
  404: "not_found",
  409: "conflict",
  413: "payload_too_large",
  429: "throttled",
  503: "backend_waking",
};

const NETWORK_MESSAGE = "Can't reach Rumor Zero. Check your connection and try again.";
const GENERIC_MESSAGE = "Something went wrong. Try again.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseRetryAfter(headers?: Headers, now = Date.now()): number | null {
  const value = headers?.get("retry-after")?.trim();
  if (!value) return null;
  if (/^\d+$/.test(value)) return Number(value);
  const date = Date.parse(value);
  return Number.isNaN(date) ? null : Math.max(0, Math.ceil((date - now) / 1000));
}

/** DRF validation errors, flattened: `{"sources": [{"value": ["Bad URL"]}]}` → `sources.0.value`. */
function collectFieldErrors(value: unknown, prefix: string, out: FieldErrors): void {
  if (typeof value === "string") {
    (out[prefix || "non_field_errors"] ??= []).push(value);
  } else if (Array.isArray(value)) {
    value.forEach((item, index) =>
      collectFieldErrors(item, typeof item === "string" ? prefix : `${prefix}.${index}`, out),
    );
  } else if (isRecord(value)) {
    for (const [key, item] of Object.entries(value)) {
      collectFieldErrors(item, prefix ? `${prefix}.${key}` : key, out);
    }
  }
}

function isAllauth(body: Record<string, unknown>): body is Record<string, unknown> & AllauthBody {
  return typeof body.status === "number" && ("errors" in body || "meta" in body || "data" in body);
}

/** One error shape for every failure (ARCHITECTURE §9 "Errors"). Pure, so it is unit-tested. */
export function normalizeError(status: number, body: unknown, headers?: Headers): ApiError {
  const retryAfter = parseRetryAfter(headers);
  const fallbackCode = DEFAULT_CODES[status] ?? `http_${status}`;
  const fallbackDetail = status === 0 ? NETWORK_MESSAGE : GENERIC_MESSAGE;

  if (!isRecord(body)) {
    return new ApiError({ status, code: fallbackCode, detail: fallbackDetail, retryAfter });
  }

  if (isAllauth(body)) {
    const errors = Array.isArray(body.errors) ? body.errors : [];
    const fieldErrors: FieldErrors = {};
    for (const error of errors) {
      (fieldErrors[error.param ?? "non_field_errors"] ??= []).push(error.message);
    }
    return new ApiError({
      status,
      code: errors[0]?.code ?? fallbackCode,
      detail: errors[0]?.message ?? fallbackDetail,
      fieldErrors,
      retryAfter,
    });
  }

  if (typeof body.detail === "string") {
    return new ApiError({
      status,
      code: typeof body.code === "string" ? body.code : fallbackCode,
      detail: body.detail,
      retryAfter,
    });
  }

  const fieldErrors: FieldErrors = {};
  collectFieldErrors(body, "", fieldErrors);
  const first = Object.values(fieldErrors)[0]?.[0];
  return new ApiError({
    status,
    code: first ? "invalid" : fallbackCode,
    detail: first ?? fallbackDetail,
    fieldErrors,
    retryAfter,
  });
}

let accessTokenGetter: () => string | null = () => null;
let unauthorizedHandler: (() => Promise<boolean>) | null = null;
let pendingUnauthorized: Promise<boolean> | null = null;

/** The AuthProvider registers where the in-memory access token lives. */
export function setAccessTokenGetter(getter: () => string | null): void {
  accessTokenGetter = getter;
}

/**
 * Called on a 401 from an app endpoint. Resolve true after refreshing the token to retry the
 * request once. Concurrent 401s share one call. Part 1 wires the refresh in.
 */
export function setUnauthorizedHandler(handler: (() => Promise<boolean>) | null): void {
  unauthorizedHandler = handler;
}

function onUnauthorized(): Promise<boolean> {
  if (!unauthorizedHandler) return Promise.resolve(false);
  pendingUnauthorized ??= unauthorizedHandler()
    .catch(() => false)
    .finally(() => {
      pendingUnauthorized = null;
    });
  return pendingUnauthorized;
}

export interface RequestOptions {
  method?: string;
  /** A plain value is sent as JSON; FormData and Blob bodies are sent as they are. */
  body?: unknown;
  headers?: HeadersInit;
  signal?: AbortSignal;
  /** Defaults to "auth" for `/auth/...` paths, else "app". */
  kind?: ApiKind;
}

function isRawBody(body: unknown): body is BodyInit {
  return (
    (typeof FormData !== "undefined" && body instanceof FormData) ||
    (typeof Blob !== "undefined" && body instanceof Blob)
  );
}

async function readJson(response: Response): Promise<unknown> {
  if (!(response.headers.get("content-type") ?? "").includes("json")) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * `path` is relative to "/api", e.g. `/v1/posts/` or `/auth/app/v1/auth/login`. Resolves with the
 * parsed JSON (undefined for empty responses) or throws an `ApiError`.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new Error(`API paths start with one "/": ${path}`);
  }
  const kind = options.kind ?? (path.startsWith("/auth/") ? "auth" : "app");
  const url = baseFor(kind) + path;

  const send = (): Promise<Response> => {
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    headers.set("X-Requested-With", "rumor-zero");
    let body: BodyInit | undefined;
    if (options.body !== undefined) {
      if (isRawBody(options.body)) {
        body = options.body;
      } else {
        headers.set("Content-Type", "application/json");
        body = JSON.stringify(options.body);
      }
    }
    const token = accessTokenGetter();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal,
      credentials: "same-origin",
    });
  };

  const attempt = async (): Promise<Response> => {
    try {
      return await send();
    } catch (error) {
      if (options.signal?.aborted) throw error;
      throw normalizeError(0, null);
    }
  };

  let response = await attempt();
  if (response.status === 401 && kind === "app" && (await onUnauthorized())) {
    response = await attempt();
  }

  if (!response.ok) {
    throw normalizeError(response.status, await readJson(response), response.headers);
  }
  if (response.status === 204 || response.status === 205) return undefined as T;
  return (await readJson(response)) as T;
}

type Options = Omit<RequestOptions, "method" | "body">;

export const api = {
  get: <T>(path: string, options?: Options) => apiFetch<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Options) =>
    apiFetch<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: Options) =>
    apiFetch<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: Options) =>
    apiFetch<T>(path, { ...options, method: "PATCH", body }),
  del: <T = void>(path: string, options?: Options) =>
    apiFetch<T>(path, { ...options, method: "DELETE" }),
};
