import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive" | "icon";

const BASE =
  "inline-flex items-center justify-center gap-space-xs rounded-lg font-body-md text-body-md font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60";

const VARIANT: Record<ButtonVariant, string> = {
  primary:
    "px-space-md py-space-sm bg-secondary text-on-secondary shadow-sm hover:bg-on-secondary-container",
  secondary:
    "px-space-md py-space-sm border border-outline-variant bg-surface-container-lowest text-on-surface hover:bg-surface-container-low",
  ghost:
    "px-space-md py-space-sm text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
  destructive:
    "px-space-md py-space-sm bg-error text-on-error shadow-sm hover:bg-on-error-container",
  icon: "p-space-xs text-outline hover:bg-surface-container-low hover:text-on-surface",
};

/** Class string for a Button look, so links (next/link) can be styled like buttons. */
export function buttonClasses({
  variant = "primary",
  block,
  className,
}: {
  variant?: ButtonVariant;
  /** Full width, 44px tall: the auth-card call to action. */
  block?: boolean;
  className?: string;
} = {}): string {
  return cn(BASE, VARIANT[variant], block && "h-11 w-full", className);
}

type CommonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  block?: boolean;
  /** Shows a spinner, sets aria-busy and ignores clicks. */
  loading?: boolean;
  children?: ReactNode;
};

export type ButtonProps =
  | (CommonProps & { variant?: Exclude<ButtonVariant, "icon"> })
  // An icon-only button has no text, so it must be named.
  | (CommonProps & { variant: "icon"; "aria-label": string });

export function Button({
  variant = "primary",
  block,
  loading,
  className,
  type = "button",
  disabled,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClasses({ variant, block, className })}
    >
      {loading && (
        <Icon name="progress_activity" className="animate-spin motion-reduce:animate-none" />
      )}
      {children}
    </button>
  );
}
