"use client";

import { createContext, useContext } from "react";

/**
 * Lets the page that deleted the account tell the app frame to leave quietly. A signed-out visitor
 * on `/settings` is normally sent to `/login?next=/settings`; after a deletion the right place is
 * `/home` (public), so the frame must not redirect. The frame provides `begin`.
 */
export interface AccountExit {
  /** Call just before the session ends. */
  begin: () => void;
}

export const AccountExitContext = createContext<AccountExit | null>(null);

export function useAccountExit(): AccountExit {
  return useContext(AccountExitContext) ?? { begin: () => {} };
}
