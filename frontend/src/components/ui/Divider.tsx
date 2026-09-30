import { cn } from "@/lib/cn";

/** Hairline rule, optionally with a centred label such as "or continue with email" (Stitch a2). */
export function Divider({ label, className }: { label?: string; className?: string }) {
  if (!label) {
    return <hr className={cn("border-t border-outline-variant/30", className)} />;
  }
  return (
    <div
      role="separator"
      aria-label={label}
      className={cn("relative flex items-center", className)}
    >
      <div aria-hidden="true" className="absolute inset-0 flex items-center">
        <div className="w-full border-t border-outline-variant/30" />
      </div>
      <span className="relative mx-auto bg-surface-container-lowest px-space-md font-body-sm text-body-sm text-outline select-none">
        {label}
      </span>
    </div>
  );
}
