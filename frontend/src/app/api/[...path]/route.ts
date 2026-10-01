// The API relay (ARCHITECTURE §1): every /api/* request goes to Django. The logic lives in
// src/lib/api/relay.ts, because a route file may only export route handlers and route config.
// Not Next's proxy.ts (ANALYSIS c-36).
import { createRelay } from "@/lib/api/relay";

const relay = createRelay();

export const GET = relay;
export const HEAD = relay;
export const POST = relay;
export const PUT = relay;
export const PATCH = relay;
export const DELETE = relay;
export const OPTIONS = relay;
