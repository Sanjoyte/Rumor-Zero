import { type InputHTMLAttributes, type ReactNode, useId } from "react";
import { cn } from "@/lib/cn";

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  description?: ReactNode;
  wrapperClassName?: string;
}

/**
 * Stitch c2 (and a3) checkbox: Protocol Blue when checked, label and optional description. A
 * caller's `aria-describedby` (an error under it) is kept and joined with the description's id.
 */
export function Checkbox({
  label,
  description,
  wrapperClassName,
  className,
  id,
  "aria-describedby": describedBy,
  ...rest
}: CheckboxProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const descriptionId = description ? `${inputId}-description` : undefined;
  const describedByIds = [describedBy, descriptionId].filter(Boolean).join(" ") || undefined;
  return (
    <label
      htmlFor={inputId}
      className={cn(
        "flex cursor-pointer items-start gap-space-md has-disabled:cursor-not-allowed has-disabled:opacity-60",
        wrapperClassName,
      )}
    >
      <input
        {...rest}
        id={inputId}
        type="checkbox"
        aria-describedby={describedByIds}
        className={cn(
          "mt-0.5 form-checkbox cursor-pointer rounded-lg border-outline-variant text-secondary focus:ring-secondary/30 focus:ring-offset-0",
          className,
        )}
      />
      <span>
        <span className="block font-body-sm text-body-sm font-semibold text-on-surface">
          {label}
        </span>
        {description && (
          <span id={descriptionId} className="block font-body-sm text-body-sm text-outline">
            {description}
          </span>
        )}
      </span>
    </label>
  );
}
