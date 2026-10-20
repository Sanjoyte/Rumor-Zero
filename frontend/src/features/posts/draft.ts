import type { PostType } from "@/lib/api/types";
import type { SourceRow } from "./sources";

/** What the composer holds between openings: it survives Cancel, Esc and ×; only a successful
 * post or a change of user clears it. In memory only, never in storage. */
export interface Draft {
  content: string;
  /** null until the author chooses: there is no default (ANALYSIS b-2). */
  postType: PostType | null;
  /** Always at least one row; empty rows are dropped when sending. */
  rows: SourceRow[];
  /** The emergency toggle (a fact only, Part 11C) and its required confirmation. */
  emergency: boolean;
  confirmed: boolean;
}

let rowSequence = 0;

export function newRow(text = ""): SourceRow {
  rowSequence += 1;
  return { id: `source-${rowSequence}`, text };
}

export function emptyDraft(): Draft {
  return { content: "", postType: null, rows: [newRow()], emergency: false, confirmed: false };
}

export function isEmptyDraft(draft: Draft): boolean {
  return (
    draft.content === "" &&
    draft.postType === null &&
    draft.rows.every((row) => row.text === "") &&
    !draft.emergency
  );
}
