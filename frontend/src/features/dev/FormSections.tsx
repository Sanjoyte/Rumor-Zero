"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Divider } from "@/components/ui/Divider";
import { Icon } from "@/components/ui/Icon";
import { PasswordField } from "@/components/ui/PasswordField";
import { RadioCardGroup } from "@/components/ui/RadioCard";
import { Select } from "@/components/ui/Select";
import { TextField } from "@/components/ui/TextField";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import { Section, Specimen } from "./GalleryLayout";

const REASONS = [
  {
    value: "inaccurate",
    label: "False or inaccurate",
    description: "The claim is wrong or not supported by the evidence.",
  },
  {
    value: "misleading",
    label: "Missing context or misleading",
    description: "True on its own, but it leaves out something important.",
  },
  {
    value: "harassment",
    label: "Harassment or defamation",
    description: "It targets a person or group.",
  },
  {
    value: "spam",
    label: "Spam or fake accounts",
    description: "Promotion or inauthentic activity.",
  },
  { value: "other", label: "Something else", description: "Tell us more in the details." },
];

export function FormSections() {
  const [reason, setReason] = useState<string | null>("inaccurate");
  const [on, setOn] = useState(false);
  const [emergency, setEmergency] = useState(true);
  const [checked, setChecked] = useState(true);

  return (
    <>
      <Section
        id="icons"
        title="Icon"
        note="Material Symbols Outlined, self-hosted. Sizes are the DESIGN.md scale."
      >
        <Specimen label="sizes xs, sm, md, lg, xl, 2xl, 3xl" className="items-center">
          {(["xs", "sm", "md", "lg", "xl", "2xl", "3xl"] as const).map((size) => (
            <Icon key={size} name="verified" size={size} className="text-primary" />
          ))}
        </Specimen>
        <Specimen label="outlined and filled" className="items-center">
          <Icon name="bolt" size="xl" className="text-tertiary" />
          <Icon name="bolt" size="xl" filled className="text-tertiary" />
        </Specimen>
      </Section>

      <Section id="buttons" title="Button">
        <Specimen label="variants">
          <Button>Submit</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Cancel</Button>
          <Button variant="destructive">Delete account</Button>
          <Button variant="icon" aria-label="More options">
            <Icon name="more_horiz" size="xl" />
          </Button>
        </Specimen>
        <Specimen label="states">
          <Button disabled>Disabled</Button>
          <Button loading>Saving</Button>
          <Button variant="secondary" disabled>
            Disabled
          </Button>
        </Specimen>
        <Specimen label="block (auth card call to action)" className="max-w-form">
          <Button block>Create account</Button>
        </Specimen>
      </Section>

      <Section id="fields" title="TextField, PasswordField, Textarea">
        <div className="grid max-w-wide gap-space-lg md:grid-cols-2">
          <TextField label="Email" type="email" placeholder="you@example.com" />
          <TextField label="Username" hint="3 to 30 characters: letters, numbers, underscores." />
          <TextField
            label="Email"
            defaultValue="not-an-email"
            error="Enter a valid email address."
          />
          <TextField label="Source" leadingIcon="link" mono placeholder="https://" />
          <TextField label="Disabled" disabled defaultValue="Read only" />
          <PasswordField label="Password" defaultValue="hunter2hunter2" />
        </div>
        <div className="grid max-w-wide gap-space-lg md:grid-cols-2">
          <Textarea label="Bio" maxCount={280} defaultValue="Reads the footnotes." />
          <Textarea label="Bio" maxCount={10} defaultValue="Way over the limit" />
          <Textarea label="Post text" variant="bare" placeholder="What do you want to say?" />
        </div>
      </Section>

      <Section id="choices" title="Checkbox, RadioCard, Select, Toggle, Divider">
        <div className="grid max-w-wide gap-space-lg md:grid-cols-2">
          <div className="space-y-space-md">
            <Checkbox
              label="Email me about replies"
              description="At most one email a day."
              checked={checked}
              onChange={(event) => setChecked(event.target.checked)}
            />
            <Checkbox label="Unchecked" />
            <Checkbox label="Disabled" disabled />
          </div>
          <div className="space-y-space-md">
            <Select label="Type" inline defaultValue="all">
              <option value="all">All posts</option>
              <option value="fact">Facts</option>
            </Select>
            <Select label="Sort by" defaultValue="newest">
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
            </Select>
          </div>
        </div>
        <Specimen
          label="toggle: off, on (blue), on (emergency violet), disabled"
          className="items-center"
        >
          <Toggle label="Off" checked={on} onCheckedChange={setOn} />
          <Toggle label="On" checked onCheckedChange={() => {}} />
          <Toggle
            label="Emergency"
            tone="tertiary"
            checked={emergency}
            onCheckedChange={setEmergency}
          />
          <Toggle label="Disabled" checked={false} onCheckedChange={() => {}} disabled />
        </Specimen>
        <div className="max-w-modal">
          <RadioCardGroup
            name="gallery-reason"
            legend="Why are you reporting this post?"
            options={REASONS}
            value={reason}
            onChange={setReason}
          />
        </div>
        <div className="max-w-form bg-surface-container-lowest p-space-lg">
          <Divider label="or continue with email" />
        </div>
      </Section>
    </>
  );
}
