import { type InputHTMLAttributes, type ReactNode, useId } from "react";
import { cn } from "@/lib/cn";
import {
  CONTROL_BASE,
  CONTROL_FONT,
  CONTROL_FONT_MONO,
  ERROR_CLASSES,
  HINT_CLASSES,
  LABEL_CLASSES,
  SUCCESS_CLASSES,
  controlColor,
} from "./field-styles";
import { Icon } from "./Icon";

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label: string;
  /** Visually hide the label (it is still the accessible name). */
  hideLabel?: boolean;
  hint?: ReactNode;
  error?: ReactNode;
  /** A confirmation in Verified teal, such as "Available: @ada" (Stitch a2). */
  success?: ReactNode;
  /** Monospace text, for URLs and identifiers such as a DOI. */
  mono?: boolean;
  /** Decorative glyph inside the left edge of the input (a Material Symbols name). */
  leadingIcon?: string;
  /** Interactive or decorative content inside the right edge (for example the show/hide button). */
  trailing?: ReactNode;
  wrapperClassName?: string;
}

export function TextField({
  label,
  hideLabel,
  hint,
  error,
  success,
  mono,
  leadingIcon,
  trailing,
  wrapperClassName,
  className,
  id,
  type = "text",
  ...rest
}: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const successId = success && !error ? `${inputId}-success` : undefined;
  const describedBy = [rest["aria-describedby"], errorId, successId, hintId]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={cn("space-y-space-xs", wrapperClassName)}>
      <label htmlFor={inputId} className={cn(LABEL_CLASSES, hideLabel && "sr-only")}>
        {label}
      </label>
      <div className="relative">
        {leadingIcon && (
          <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-space-md text-outline">
            <Icon name={leadingIcon} />
          </span>
        )}
        <input
          {...rest}
          id={inputId}
          type={type}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          className={cn(
            "form-input h-11 px-space-md py-space-sm",
            CONTROL_BASE,
            mono ? CONTROL_FONT_MONO : CONTROL_FONT,
            controlColor(Boolean(error)),
            leadingIcon && "pl-9",
            Boolean(trailing) && "pr-10",
            className,
          )}
        />
        {trailing && (
          <div className="absolute inset-y-0 right-0 flex items-center pr-space-md">{trailing}</div>
        )}
      </div>
      {error && (
        <p id={errorId} className={ERROR_CLASSES}>
          <Icon name="error" size="sm" />
          {error}
        </p>
      )}
      {success && !error && (
        <p id={successId} className={SUCCESS_CLASSES}>
          <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
          {success}
        </p>
      )}
      {hint && (
        <p id={hintId} className={HINT_CLASSES}>
          {hint}
        </p>
      )}
    </div>
  );
}
