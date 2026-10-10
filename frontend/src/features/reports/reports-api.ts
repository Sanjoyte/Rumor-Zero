/**
 * The report endpoint (ARCHITECTURE §5, §9, Part 8). An ordinary app call: it sends the in-memory
 * access token and gets the client's single refresh-and-retry on a 401.
 */
import { api } from "@/lib/api/client";
import type { ReportReason } from "./reasons";

export const REPORT_PATHS = {
  report: (postId: string) => `/v1/posts/${encodeURIComponent(postId)}/report/`,
} as const;

export interface ReportBody {
  reason: ReportReason;
  /** Trimmed. Required by the server when the reason is "other". */
  details: string;
}

export function reportPost(postId: string, body: ReportBody): Promise<{ reported: true }> {
  return api.post<{ reported: true }>(REPORT_PATHS.report(postId), body);
}
