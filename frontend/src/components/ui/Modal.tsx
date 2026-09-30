"use client";

import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef } from "react";
import { cn } from "@/lib/cn";
import { Button } from "./Button";
import { Icon } from "./Icon";

export interface ModalProps {
  open: boolean;
  /** Called for Esc, the close button and (optionally) a click on the scrim. */
  onClose: () => void;
  title: string;
  /** Glyph before the title (Stitch b2 uses edit_note). */
  icon?: string;
  /** Small caps line above the title (Stitch d1). */
  eyebrow?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** The Stitch composer footer is a light grey band (low); the report modal uses plain white. */
  footerTone?: "low" | "plain";
  dismissOnBackdrop?: boolean;
  className?: string;
}

const FOCUSABLE =
  "textarea, input:not([type=hidden]), select, button, a[href], [tabindex]:not([tabindex='-1'])";

/**
 * Modal dialog on the native dialog element: the browser provides the top layer, the scrim and the
 * focus trap. Esc closes it, and focus returns to whatever opened it. Mark an element with
 * data-autofocus to choose where focus lands on open.
 */
export function Modal({
  open,
  onClose,
  title,
  icon,
  eyebrow,
  children,
  footer,
  footerTone = "low",
  dismissOnBackdrop = false,
  className,
}: ModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const openRef = useRef(open);
  const titleId = useId();

  useEffect(() => {
    openRef.current = open;
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      returnFocusRef.current = document.activeElement as HTMLElement | null;
      dialog.showModal();
      // querySelector on a selector list returns the first match in document order, so look for
      // the marked element first and only then fall back to the first focusable one.
      const target =
        dialog.querySelector<HTMLElement>("[data-autofocus]") ??
        dialog.querySelector<HTMLElement>(FOCUSABLE);
      (target ?? dialog).focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  function handleClose() {
    // The dialog closed: give focus back, and tell the parent if it did not ask for this.
    returnFocusRef.current?.focus();
    if (openRef.current) onClose();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      aria-modal="true"
      onClose={handleClose}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onKeyDown={handleKeyDown}
      onClick={(event) => {
        if (dismissOnBackdrop && event.target === event.currentTarget) onClose();
      }}
      className={cn(
        "m-auto w-[calc(100%-2.5rem)] max-w-modal bg-transparent p-0 text-on-surface",
        "backdrop:bg-inverse-surface/40 backdrop:backdrop-blur-[2px]",
        className,
      )}
    >
      <div className="flex max-h-[90dvh] flex-col overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-lowest shadow-sm">
        <div className="flex items-center justify-between gap-space-md border-b border-outline-variant/30 px-space-lg py-space-md">
          <div className="min-w-0">
            {eyebrow && (
              <p className="font-label-code text-label-badge font-bold tracking-wider text-on-surface-variant uppercase">
                {eyebrow}
              </p>
            )}
            <h2
              id={titleId}
              className="flex items-center gap-space-sm font-headline-sm text-headline-sm text-on-surface"
            >
              {icon && <Icon name={icon} size="lg" className="text-secondary" />}
              {title}
            </h2>
          </div>
          <Button variant="icon" aria-label="Close" onClick={onClose}>
            <Icon name="close" className="block" />
          </Button>
        </div>
        <div className="space-y-space-lg overflow-y-auto p-space-lg">{children}</div>
        {footer && (
          <div
            className={cn(
              "flex items-center justify-between gap-space-md border-t border-outline-variant/30 px-space-lg py-space-md",
              footerTone === "low" ? "bg-surface-container-low" : "bg-surface-container-lowest",
            )}
          >
            {footer}
          </div>
        )}
      </div>
    </dialog>
  );
}
