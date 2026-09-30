"use client";

import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { cn } from "@/lib/cn";
import { Icon } from "./Icon";

export type ToastTone = "neutral" | "success" | "error";

export const TOAST_DURATION_MS = 4000;

const GLYPH: Record<ToastTone, { name: string; className: string }> = {
  neutral: { name: "info", className: "text-inverse-on-surface" },
  success: { name: "check_circle", className: "text-inverse-primary" },
  error: { name: "error", className: "text-error-container" },
};

/** The dark pill itself. Stitch has no toast, so it is built from tokens. Also used in the gallery. */
export function Toast({
  message,
  tone = "neutral",
  onDismiss,
}: {
  message: ReactNode;
  tone?: ToastTone;
  onDismiss?: () => void;
}) {
  const glyph = GLYPH[tone];
  return (
    <div className="pointer-events-auto flex items-center gap-space-sm rounded-lg bg-inverse-surface px-space-md py-space-sm font-body-sm text-body-sm text-inverse-on-surface shadow-sm">
      <Icon name={glyph.name} className={cn("shrink-0", glyph.className)} />
      <span>{message}</span>
      {onDismiss && (
        <button
          type="button"
          aria-label="Dismiss"
          onClick={onDismiss}
          className="ml-space-xs shrink-0 rounded-lg p-0.5 opacity-80 hover:opacity-100"
        >
          <Icon name="close" size="sm" />
        </button>
      )}
    </div>
  );
}

interface ToastItem {
  id: number;
  message: ReactNode;
  tone: ToastTone;
}

interface ToastApi {
  show: (message: ReactNode, options?: { tone?: ToastTone }) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast must be used inside a ToastProvider");
  return api;
}

let nextId = 0;

/** Bottom-centre toasts that clear themselves after 4 seconds. Mounted once, in app/providers.tsx. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const show = useCallback<ToastApi["show"]>((message, options) => {
    nextId += 1;
    const item = { id: nextId, message, tone: options?.tone ?? "neutral" };
    setItems((current) => [...current, item]);
  }, []);

  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed right-0 bottom-space-lg left-0 z-50 flex flex-col items-center gap-space-sm px-space-lg"
      >
        {items.map((item) => (
          <ToastEntry key={item.id} item={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastEntry({ item, onDismiss }: { item: ToastItem; onDismiss: (id: number) => void }) {
  const expire = useCallback(() => onDismiss(item.id), [onDismiss, item.id]);
  useEffect(() => {
    const timer = setTimeout(expire, TOAST_DURATION_MS);
    return () => clearTimeout(timer);
  }, [expire]);
  return <Toast message={item.message} tone={item.tone} onDismiss={expire} />;
}
