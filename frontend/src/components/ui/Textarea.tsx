"use client";

import {
  type ChangeEvent,
  type ReactNode,
  type TextareaHTMLAttributes,
  useId,
  useState,
} from "react";
import { cn } from "@/lib/cn";
import {
  CONTROL_BASE,
  CONTROL_FONT,
  ERROR_CLASSES,
  HINT_CLASSES,
  LABEL_CLASSES,
  controlColor,
} from "./field-styles";
import { Icon } from "./Icon";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hideLabel?: boolean;
  hint?: ReactNode;
  error?: ReactNode;
  /**
   * "filled" is the settings-form look (c2). "bare" is the composer look (b2): large serif claim
   * text straight on the page, no border, with the label hidden.
   */
  variant?: "filled" | "bare";
  /** Shows "n / max characters". The counter turns red over the limit. */
  maxCount?: number;
  wrapperClassName?: string;
}

export function Textarea({
  label,
  hideLabel,
  hint,
  error,
  variant = "filled",
  maxCount,
  wrapperClassName,
  className,
  id,
  value,
  defaultValue,
  onChange,
  rows = 3,
  ...rest
}: TextareaProps) {
  const autoId = useId();
  const textareaId = id ?? autoId;
  const hintId = hint ? `${textareaId}-hint` : undefined;
  const errorId = error ? `${textareaId}-error` : undefined;
  const counterId = maxCount !== undefined ? `${textareaId}-count` : undefined;
  const [innerLength, setInnerLength] = useState(String(defaultValue ?? "").length);
  const length = value !== undefined ? String(value).length : innerLength;
  const over = maxCount !== undefined && length > maxCount;
  const describedBy = [rest["aria-describedby"], errorId, hintId, counterId]
    .filter(Boolean)
    .join(" ");

  function handleChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setInnerLength(event.target.value.length);
    onChange?.(event);
  }

  return (
    <div className={cn("space-y-space-xs", wrapperClassName)}>
      <label
        htmlFor={textareaId}
        className={cn(LABEL_CLASSES, (hideLabel || variant === "bare") && "sr-only")}
      >
        {label}
      </label>
      <textarea
        {...rest}
        id={textareaId}
        rows={rows}
        value={value}
        defaultValue={defaultValue}
        onChange={handleChange}
        aria-invalid={error || over ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={cn(
          variant === "bare"
            ? "min-h-[90px] w-full resize-none form-textarea border-none bg-transparent p-0 font-claim-headline text-claim-headline text-on-surface placeholder:text-outline focus:ring-0"
            : cn(
                "form-textarea px-space-md py-space-sm",
                CONTROL_BASE,
                CONTROL_FONT,
                controlColor(Boolean(error) || over),
              ),
          className,
        )}
      />
      {maxCount !== undefined && (
        <p
          id={counterId}
          className={cn(
            "text-right font-label-code text-label-badge tabular-nums",
            over ? "text-error" : "text-outline",
          )}
        >
          {length} / {maxCount} characters
        </p>
      )}
      {error && (
        <p id={errorId} className={ERROR_CLASSES}>
          <Icon name="error" size="sm" />
          {error}
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
