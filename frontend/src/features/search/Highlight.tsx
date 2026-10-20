import { Fragment } from "react";
import { splitByTerms } from "./highlight";

/**
 * `text` with the words that match `terms` in `<mark>` (Stitch b4's yellow highlight). Plain text
 * in, text nodes out: React escapes everything, so a result that looks like HTML stays text. Inside
 * an italic opinion the mark stays upright (`not-italic`).
 */
export function Highlight({ text, terms }: { text: string; terms: readonly string[] }) {
  return (
    <>
      {splitByTerms(text, terms).map((part, index) =>
        part.match ? (
          <mark
            key={index}
            className="rounded-lg bg-secondary-fixed px-space-xs py-0.5 text-on-secondary-fixed not-italic"
          >
            {part.text}
          </mark>
        ) : (
          <Fragment key={index}>{part.text}</Fragment>
        ),
      )}
    </>
  );
}
