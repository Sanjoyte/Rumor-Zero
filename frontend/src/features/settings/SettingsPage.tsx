"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { Icon } from "@/components/ui/Icon";
import { Skeleton } from "@/components/ui/Skeleton";
import { DangerAction, DangerZone } from "@/components/ui/DangerZone";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { CredibilityPanel } from "@/features/reputation/CredibilityPanel";
import { useAuth } from "@/lib/auth/AuthProvider";
import { AccountSection } from "./AccountSection";
import { useAccountExit } from "./account-exit";
import { AvatarUploader } from "./AvatarUploader";
import { DataExportCard } from "./DataExportCard";
import { DeleteAccountModal } from "./DeleteAccountModal";
import { SETTINGS_MESSAGES } from "./messages";
import { ProfileForm } from "./ProfileForm";

const SECTIONS = [
  { id: "section-profile", label: "Profile", icon: "badge" },
  { id: "section-account", label: "Account", icon: "shield" },
  { id: "section-credibility", label: "Credibility", icon: "military_tech" },
  { id: "section-data", label: "Your data", icon: "lock" },
] as const;

function Section({
  id,
  number,
  title,
  description,
  children,
}: {
  id: string;
  number: string;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-24 space-y-space-lg">
      <div className="border-b border-outline-variant/30 pb-space-md">
        <p className="font-label-code text-label-badge tracking-wider text-outline uppercase">
          Section {number}
        </p>
        <h2 id={`${id}-title`} className="font-headline-sm text-headline-sm text-on-surface">
          {title}
        </h2>
        <p className="font-body-sm text-body-sm text-outline">{description}</p>
      </div>
      {children}
    </section>
  );
}

/**
 * `/settings` (Stitch c2): profile, account and security, your credibility, your data and the
 * danger zone. Everything here is yours, so it needs a login (the app frame already holds a
 * skeleton until the session is back).
 */
export function SettingsPage() {
  const { user, endSession } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const exit = useAccountExit();
  const [deleting, setDeleting] = useState(false);

  if (!user) {
    return (
      <div className="mx-auto w-full max-w-reading px-margin-mobile py-space-xl md:px-space-lg">
        <Skeleton className="h-10 w-48" />
      </div>
    );
  }

  const isStaff = user.role !== "user";

  function onDeleted() {
    // The frame must not send a signed-out visitor to /login?next=/settings.
    exit.begin();
    endSession();
    router.replace("/home");
    toast.show(SETTINGS_MESSAGES.accountDeleted);
  }

  return (
    <div className="mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg">
      <header>
        <p className="mb-space-sm font-label-code text-label-badge tracking-wider text-outline uppercase">
          Your account
        </p>
        <h1 className="mb-space-sm font-headline-lg text-headline-lg text-on-surface">Settings</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">
          Edit your public profile, change your password, download your data or delete your account.
        </p>
      </header>

      <nav
        aria-label="Settings sections"
        className="flex flex-wrap items-center border-b border-outline-variant/30 pb-space-sm"
      >
        {SECTIONS.map((section) => (
          <a
            key={section.id}
            href={`#${section.id}`}
            className="flex items-center gap-space-sm rounded-lg px-space-md py-space-sm font-body-md text-body-md text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface"
          >
            <Icon name={section.icon} />
            {section.label}
          </a>
        ))}
      </nav>

      <div className="space-y-12">
        <Section
          id="section-profile"
          number="01"
          title="Profile"
          description="What other people see next to your posts."
        >
          <AvatarUploader user={user} />
          <ProfileForm user={user} />
        </Section>

        <Section
          id="section-account"
          number="02"
          title="Account"
          description="Your email, your password and how you sign in."
        >
          <AccountSection user={user} />
        </Section>

        <Section
          id="section-credibility"
          number="03"
          title="Credibility"
          description="Your score and every event behind it. Others see the score once it has enough events."
        >
          <CredibilityPanel publicScore={user.public_score} defaultOpen />
        </Section>

        <Section
          id="section-data"
          number="04"
          title="Your data"
          description="Take a copy of what Rumor Zero stores about you, or delete the account."
        >
          <DataExportCard username={user.username} />
          <DangerZone title="Delete account" tag="Can't be undone">
            <DangerAction
              title="Delete your account"
              description={
                isStaff
                  ? SETTINGS_MESSAGES.staffAccount
                  : "Removes your profile, posts and everything else listed on the next screen, and signs you out everywhere."
              }
              action={
                isStaff ? undefined : (
                  <Button
                    variant="destructive"
                    className="shrink-0 whitespace-nowrap"
                    onClick={() => setDeleting(true)}
                  >
                    Delete account…
                  </Button>
                )
              }
            />
          </DangerZone>
        </Section>
      </div>

      <DeleteAccountModal
        open={deleting}
        username={user.username}
        hasPassword={user.has_usable_password}
        onClose={() => setDeleting(false)}
        onDeleted={onDeleted}
      />
    </div>
  );
}
