import { Card } from "@/components/ui/Card";
import { Icon } from "@/components/ui/Icon";

const FEATURES = [
  {
    icon: "edit_note",
    title: "1. You say what it is",
    text: "When you write, you choose Opinion or Fact. Nobody has to guess which kind of post they are reading.",
  },
  {
    icon: "assignment_turned_in",
    title: "2. Facts are checked",
    text: "A fact post is checked, and a moderator looks at anything the check is unsure about or people report.",
  },
  {
    icon: "visibility",
    title: "3. Colour means the result",
    text: "Green, red and amber show a verdict and nothing else. The label always says it in words too.",
  },
] as const;

/** Three plain-language cards (Stitch a1 "FeaturePillars", copy rewritten). */
export function FeatureCards() {
  return (
    <section aria-label="How it works" className="mx-auto mb-20 max-w-wide px-space-lg">
      <ul className="grid grid-cols-1 gap-space-lg md:grid-cols-3">
        {FEATURES.map((feature) => (
          <li key={feature.title}>
            <Card className="h-full p-space-lg">
              <h2 className="mb-space-sm flex items-center gap-space-sm font-body-md text-body-md font-semibold text-on-surface">
                <Icon name={feature.icon} size="sm" className="text-on-surface-variant" />
                {feature.title}
              </h2>
              <p className="font-body-sm text-body-sm text-on-surface-variant">{feature.text}</p>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  );
}
