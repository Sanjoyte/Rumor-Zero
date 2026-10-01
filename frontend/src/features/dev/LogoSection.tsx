import { Logo, type LogoSize, type LogoVariant } from "@/components/ui/Logo";
import { cn } from "@/lib/cn";
import { Section } from "./GalleryLayout";

const SURFACES = [
  { name: "surface", className: "bg-surface", label: "text-outline" },
  {
    name: "surface-container-lowest",
    className: "bg-surface-container-lowest",
    label: "text-outline",
  },
  { name: "inverse-surface", className: "bg-inverse-surface", label: "text-inverse-on-surface" },
] as const;

const SIZES: LogoSize[] = ["sm", "md", "lg"];
const VARIANTS: LogoVariant[] = ["wordmark", "mark"];

/** Part 0D: every Logo variant and size on the three surfaces it appears on. */
export function LogoSection() {
  return (
    <Section
      id="logo"
      title="Logo"
      note="The only brand mark in the UI. Sizes sm, md and lg are 24, 36 and 48 px tall. The logo's own colours stay inside the image."
    >
      {SURFACES.map((surface) => (
        <div
          key={surface.name}
          className={cn(
            "space-y-space-md rounded-lg border border-outline-variant/40 p-space-lg",
            surface.className,
          )}
        >
          <p className={cn("font-label-code text-label-code uppercase", surface.label)}>
            on {surface.name}
          </p>
          {VARIANTS.map((variant) => (
            <div key={variant} className="flex flex-wrap items-end gap-x-space-xl gap-y-space-md">
              {SIZES.map((size) => (
                <div key={size} className="space-y-space-xs">
                  <Logo variant={variant} size={size} />
                  <p className={cn("font-label-code text-label-code", surface.label)}>
                    {variant} {size}
                  </p>
                </div>
              ))}
            </div>
          ))}
          <div className="flex items-center gap-space-sm">
            <Logo variant="mark" size="sm" decorative />
            <span className={cn("font-body-md text-body-md", surface.label)}>
              Rumor Zero (decorative mark: the name is written next to it)
            </span>
          </div>
        </div>
      ))}
    </Section>
  );
}
