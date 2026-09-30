"use client";

import { type ReactNode, useId } from "react";
import { cn } from "@/lib/cn";

export interface RadioCardOption {
  value: string;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

export interface RadioCardGroupProps {
  /** Shared by the radios; it is also what the browser submits. */
  name: string;
  legend: ReactNode;
  /** Visually hide the legend (it stays the group name). */
  hideLegend?: boolean;
  options: RadioCardOption[];
  value: string | null;
  onChange: (value: string) => void;
  className?: string;
}

/** Stitch d1 list of radio cards (the report reasons). The checked card takes a blue border. */
export function RadioCardGroup({
  name,
  legend,
  hideLegend,
  options,
  value,
  onChange,
  className,
}: RadioCardGroupProps) {
  const groupId = useId();
  return (
    <fieldset className={cn("space-y-space-xs", className)}>
      <legend
        className={cn(
          "font-body-md text-body-md font-semibold text-on-surface",
          hideLegend && "sr-only",
        )}
      >
        {legend}
      </legend>
      {options.map((option) => {
        const id = `${groupId}-${option.value}`;
        return (
          <label
            key={option.value}
            htmlFor={id}
            className={cn(
              "flex items-start gap-space-md rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-space-sm transition-colors",
              "cursor-pointer hover:border-outline/50 hover:bg-surface-container-low",
              "has-checked:border-secondary has-checked:bg-secondary/5",
              "has-focus-visible:ring-2 has-focus-visible:ring-secondary/30",
              option.disabled && "cursor-not-allowed opacity-60",
            )}
          >
            <input
              id={id}
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              disabled={option.disabled}
              onChange={() => onChange(option.value)}
              className="mt-0.5 form-radio h-3.5 w-3.5 border-outline-variant text-secondary focus:ring-secondary/30"
            />
            <span className="space-y-0.5">
              <span className="block font-body-md text-body-md leading-tight font-semibold text-on-surface">
                {option.label}
              </span>
              {option.description && (
                <span className="block font-body-sm text-body-sm leading-normal text-outline">
                  {option.description}
                </span>
              )}
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}
