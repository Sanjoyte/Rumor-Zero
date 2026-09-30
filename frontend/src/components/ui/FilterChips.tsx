"use client";

import { cn } from "@/lib/cn";

export type ChipDot = "primary" | "error" | "verdict-review" | "outline-variant";

const DOT: Record<ChipDot, string> = {
  primary: "bg-primary",
  error: "bg-error",
  "verdict-review": "bg-verdict-review",
  "outline-variant": "bg-outline-variant",
};

export interface FilterChip {
  id: string;
  label: string;
  count?: number;
  /** A small status-coloured dot before the label (Stitch b4 status filters). */
  dot?: ChipDot;
}

export interface FilterChipsProps {
  chips: FilterChip[];
  selected: string[];
  onChange: (selected: string[]) => void;
  /** Allow several chips at once. By default choosing a chip replaces the previous choice. */
  multiple?: boolean;
  label: string;
  className?: string;
}

/** Toggle chips for narrowing a list (Stitch b4). Each chip is a pressed or not-pressed button. */
export function FilterChips({
  chips,
  selected,
  onChange,
  multiple,
  label,
  className,
}: FilterChipsProps) {
  function toggle(id: string) {
    if (selected.includes(id)) {
      onChange(selected.filter((item) => item !== id));
    } else {
      onChange(multiple ? [...selected, id] : [id]);
    }
  }

  return (
    <div
      role="group"
      aria-label={label}
      className={cn("flex flex-wrap items-center gap-space-sm", className)}
    >
      {chips.map((chip) => {
        const pressed = selected.includes(chip.id);
        return (
          <button
            key={chip.id}
            type="button"
            aria-pressed={pressed}
            onClick={() => toggle(chip.id)}
            className={cn(
              "flex items-center gap-space-xs rounded-lg border px-space-md py-space-xs font-body-sm text-body-sm transition-colors",
              pressed
                ? "border-inverse-surface bg-inverse-surface font-semibold text-inverse-on-surface"
                : "border-outline-variant/50 bg-surface-container-lowest font-medium text-on-surface-variant hover:bg-surface-container-low",
            )}
          >
            {chip.dot && (
              <span
                aria-hidden="true"
                className={cn("h-2 w-2 shrink-0 rounded-full", DOT[chip.dot])}
              />
            )}
            {chip.label}
            {chip.count !== undefined && (
              <span
                className={cn(
                  "ml-0.5 font-label-code text-label-code",
                  pressed ? "text-inverse-on-surface" : "text-outline",
                )}
              >
                {chip.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
