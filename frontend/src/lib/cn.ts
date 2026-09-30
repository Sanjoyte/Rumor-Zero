export type ClassValue = string | number | false | null | undefined | ClassValue[];

/** Joins class names, skipping falsy values. Tokens are unique, so no tailwind-merge. */
export function cn(...values: ClassValue[]): string {
  const out: string[] = [];
  for (const value of values) {
    if (Array.isArray(value)) {
      const nested = cn(...value);
      if (nested) out.push(nested);
    } else if (value || value === 0) {
      out.push(String(value));
    }
  }
  return out.join(" ");
}
