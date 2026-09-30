"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";
import { TextField, type TextFieldProps } from "./TextField";

export type PasswordFieldProps = Omit<TextFieldProps, "type" | "trailing" | "leadingIcon">;

/** A password input with a show/hide toggle (Stitch a2, a3, a6). */
export function PasswordField({ className, ...rest }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  return (
    <TextField
      {...rest}
      type={visible ? "text" : "password"}
      className={cn("tracking-wider", className)}
      trailing={
        <button
          type="button"
          aria-pressed={visible}
          aria-label={visible ? "Hide password" : "Show password"}
          onClick={() => setVisible((v) => !v)}
          className={cn(
            "flex items-center rounded-lg hover:text-on-surface-variant",
            visible ? "text-secondary" : "text-outline",
          )}
        >
          <Icon name={visible ? "visibility" : "visibility_off"} />
        </button>
      }
    />
  );
}
