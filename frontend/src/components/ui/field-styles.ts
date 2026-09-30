/**
 * Shared class strings for text-like controls (Stitch a2/b2/c2/d2). The valid and invalid sets are
 * alternatives, never combined: two colour utilities on one element would be won by CSS order.
 */
export const CONTROL_BASE =
  "block w-full rounded-lg border bg-surface-container-low text-on-surface placeholder:text-outline focus:bg-surface-container-lowest focus:outline-none focus:ring-2 transition-colors disabled:cursor-not-allowed disabled:opacity-60";

const VALID = "border-outline-variant/50 focus:border-secondary focus:ring-secondary/20";
const INVALID = "border-error focus:border-error focus:ring-error/20";

/** Default control text, and the monospace variant Stitch uses for URLs and DOIs (b2). */
export const CONTROL_FONT = "font-body-md text-body-md";
export const CONTROL_FONT_MONO = "font-label-code text-label-code font-normal tracking-tight";

export const LABEL_CLASSES = "block font-body-sm text-body-sm font-semibold text-on-surface";
export const HINT_CLASSES = "font-body-sm text-body-sm text-outline";
export const SUCCESS_CLASSES =
  "flex items-center gap-space-xs font-body-sm text-body-sm font-medium text-primary";
export const ERROR_CLASSES =
  "flex items-center gap-space-xs font-body-sm text-body-sm font-medium text-error";

export function controlColor(invalid?: boolean): string {
  return invalid ? INVALID : VALID;
}
