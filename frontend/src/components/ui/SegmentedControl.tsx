"use client";

import { type KeyboardEvent, useRef } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  icon?: string;
}

export interface SegmentedControlProps<T extends string> {
  options: SegmentOption<T>[];
  /** Null means nothing is chosen yet (the composer makes people pick Opinion or Fact). */
  value: T | null;
  onChange: (value: T) => void;
  label: string;
  className?: string;
}

/** Pill-shaped choice between a few options (Stitch b2 and c1). A radio group with arrow keys. */
export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: SegmentedControlProps<T>) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const selectedIndex = options.findIndex((option) => option.value === value);
  const tabbableIndex = selectedIndex === -1 ? 0 : selectedIndex;

  function move(nextIndex: number) {
    const next = options[(nextIndex + options.length) % options.length];
    onChange(next.value);
    refs.current[next.value]?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const keys: Record<string, () => void> = {
      ArrowRight: () => move(index + 1),
      ArrowDown: () => move(index + 1),
      ArrowLeft: () => move(index - 1),
      ArrowUp: () => move(index - 1),
      Home: () => move(0),
      End: () => move(options.length - 1),
    };
    const handler = keys[event.key];
    if (handler) {
      event.preventDefault();
      handler();
    }
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn(
        "grid auto-cols-fr grid-flow-col gap-space-xs rounded-full bg-surface-container p-space-xs",
        className,
      )}
    >
      {options.map((option, index) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            ref={(node) => {
              refs.current[option.value] = node;
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={index === tabbableIndex ? 0 : -1}
            onClick={() => onChange(option.value)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn(
              "flex items-center justify-center gap-space-sm rounded-full px-space-md py-space-xs font-body-sm text-body-sm transition-colors",
              selected
                ? "bg-surface-container-lowest font-semibold text-on-surface shadow-sm"
                : "text-on-surface-variant hover:text-on-surface",
            )}
          >
            {option.icon && (
              <Icon
                name={option.icon}
                size="sm"
                className={selected ? "text-secondary" : "text-outline"}
              />
            )}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
