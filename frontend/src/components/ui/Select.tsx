import { type ReactNode, type SelectHTMLAttributes, useId } from "react";
import { cn } from "@/lib/cn";
import { LABEL_CLASSES } from "./field-styles";

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "size"> {
  label: string;
  hideLabel?: boolean;
  /** Put the label on the same row as the select (Stitch d2 toolbar: Type, Sort). */
  inline?: boolean;
  wrapperClassName?: string;
  children: ReactNode;
}

/** Stitch d2 select. The arrow comes from the forms plugin via the form-select class. */
export function Select({
  label,
  hideLabel,
  inline,
  wrapperClassName,
  className,
  id,
  children,
  ...rest
}: SelectProps) {
  const autoId = useId();
  const selectId = id ?? autoId;
  return (
    <div
      className={cn(
        inline ? "flex items-center gap-space-xs" : "space-y-space-xs",
        wrapperClassName,
      )}
    >
      <label
        htmlFor={selectId}
        className={cn(
          inline
            ? "font-label-code text-label-code text-on-surface-variant uppercase"
            : LABEL_CLASSES,
          hideLabel && "sr-only",
        )}
      >
        {label}
      </label>
      <select
        {...rest}
        id={selectId}
        className={cn(
          "cursor-pointer form-select rounded-lg border border-outline-variant/50 bg-surface-container-low py-space-xs pr-10 pl-space-md font-body-sm text-body-sm text-on-surface",
          "disabled:cursor-not-allowed disabled:opacity-60",
          "focus:border-secondary focus:bg-surface-container-lowest focus:ring-2 focus:ring-secondary/20 focus:outline-none",
          className,
        )}
      >
        {children}
      </select>
    </div>
  );
}
