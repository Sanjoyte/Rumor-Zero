export type PasswordStrength = 0 | 1 | 2 | 3 | 4;

export const PASSWORD_STRENGTH_LABELS = ["", "Weak", "Fair", "Good", "Strong"] as const;

function characterClasses(password: string): number {
  return [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((re) => re.test(password)).length;
}

/**
 * Advisory strength for the sign-up and reset forms: 0 (empty) or 1-4 = Weak / Fair / Good / Strong.
 * The Django validators stay authoritative; this only guides the person typing.
 */
export function scorePassword(password: string): PasswordStrength {
  if (!password) return 0;
  const length = password.length;
  const classes = characterClasses(password);
  if (length < 8 || classes < 2) return 1;
  if (length >= 16 || (length >= 12 && classes >= 3)) return 4;
  if (length >= 12 || classes >= 3) return 3;
  return 2;
}
