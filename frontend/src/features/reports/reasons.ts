/** The five report reasons (ANALYSIS b-5; ARCHITECTURE §2): the value is what the API stores. */
export const MAX_DETAILS = 500;

export type ReportReason = "inaccurate" | "misleading" | "harassment" | "spam" | "other";

export interface ReasonOption {
  value: ReportReason;
  label: string;
  description: string;
}

export const REPORT_REASONS: ReasonOption[] = [
  {
    value: "inaccurate",
    label: "False or inaccurate",
    description: "The claim is wrong or not supported by the evidence.",
  },
  {
    value: "misleading",
    label: "Missing context or misleading",
    description: "True on its own, but it leaves out something important.",
  },
  {
    value: "harassment",
    label: "Harassment or defamation",
    description: "It targets a person or group.",
  },
  {
    value: "spam",
    label: "Spam or fake accounts",
    description: "Promotion or inauthentic activity.",
  },
  { value: "other", label: "Something else", description: "Tell us more in the details." },
];

export function isReportReason(value: string | null): value is ReportReason {
  return REPORT_REASONS.some((option) => option.value === value);
}
