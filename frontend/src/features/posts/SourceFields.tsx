"use client";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { TextField } from "@/components/ui/TextField";
import { MAX_SOURCES, type SourceRow } from "./sources";

export interface SourceFieldsProps {
  rows: SourceRow[];
  /** A message per row id. */
  errors: Record<string, string>;
  /** Shown under the rows: the list rule from the server ("You can add up to 5 sources."). */
  listError?: string;
  disabled?: boolean;
  onChange: (id: string, text: string) => void;
  onBlur: (id: string) => void;
  onAdd: () => void;
  onRemove: (id: string) => void;
}

/** The DOM id of a row's input, so the composer can focus it (a new row, or the first error). */
export function sourceInputId(rowId: string): string {
  return `composer-${rowId}`;
}

/**
 * The optional "Source (URL or DOI)" list for a fact post (Stitch b2, turned into up to five rows):
 * one row to start, "Add another source" until five, a remove button on rows 2 to 5, and an error
 * under each row that has one. Empty rows are dropped when the post is sent.
 */
export function SourceFields({
  rows,
  errors,
  listError,
  disabled,
  onChange,
  onBlur,
  onAdd,
  onRemove,
}: SourceFieldsProps) {
  return (
    <div role="group" aria-labelledby="composer-sources-label" className="space-y-space-xs">
      <div className="flex items-center justify-between gap-space-sm">
        <span
          id="composer-sources-label"
          className="font-body-sm text-body-sm font-semibold text-on-surface"
        >
          Source (URL or DOI) <span className="font-normal text-outline">(optional)</span>
        </span>
        <span className="flex shrink-0 items-center gap-space-xs font-body-sm text-body-sm font-medium text-secondary">
          <Icon name="check_circle" size="xs" />
          DOI preferred
        </span>
      </div>
      <div className="space-y-space-sm">
        {rows.map((row, index) => (
          <div key={row.id} className="flex items-start gap-space-sm">
            <TextField
              id={sourceInputId(row.id)}
              label={`Source ${index + 1}`}
              hideLabel
              mono
              leadingIcon="link"
              placeholder="https://… or a DOI"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              value={row.text}
              disabled={disabled}
              error={errors[row.id]}
              onChange={(event) => onChange(row.id, event.target.value)}
              onBlur={() => onBlur(row.id)}
              wrapperClassName="min-w-0 flex-1"
            />
            {index > 0 && (
              <Button
                variant="icon"
                aria-label={`Remove source ${index + 1}`}
                disabled={disabled}
                onClick={() => onRemove(row.id)}
                className="mt-space-xs"
              >
                <Icon name="close" size="md" />
              </Button>
            )}
          </div>
        ))}
      </div>
      {listError && (
        <p role="alert" className="font-body-sm text-body-sm text-error">
          {listError}
        </p>
      )}
      {rows.length < MAX_SOURCES && (
        <Button variant="ghost" disabled={disabled} onClick={onAdd} className="-ml-space-md">
          <Icon name="add" size="sm" />
          Add another source
        </Button>
      )}
    </div>
  );
}
