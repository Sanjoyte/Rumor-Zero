"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { buttonClasses } from "@/components/ui/Button";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import type { Me } from "@/lib/api/types";
import { ChangePasswordModal } from "./ChangePasswordModal";

function Row({
  icon,
  title,
  description,
  action,
}: {
  icon: string;
  title: string;
  description: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-space-md p-space-md">
      <div className="flex items-center gap-space-md">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-outline-variant/30 bg-surface-container text-on-surface-variant">
          <Icon name={icon} />
        </div>
        <div>
          <p className="font-body-sm text-body-sm font-semibold text-on-surface">{title}</p>
          <div className="font-body-sm text-body-sm text-outline">{description}</div>
        </div>
      </div>
      {action}
    </div>
  );
}

/** Stitch c2's Verified chip. */
function VerifiedChip() {
  return (
    <span className="inline-flex items-center gap-space-xs rounded-lg border border-primary/30 bg-primary/10 px-space-sm py-0.5 font-label-code text-label-code font-bold text-primary uppercase">
      <Icon name="check_circle" size="xs" filled />
      Verified
    </span>
  );
}

/**
 * Settings, section 2 (Stitch c2 "Account & Security"): the email and its state, the password (or
 * the way to set one for a Google-only account) and the Google link. No 2FA, sessions list or
 * email change: the account has none of them (ANALYSIS b-5).
 */
export function AccountSection({ user }: { user: Me }) {
  const [changing, setChanging] = useState(false);
  return (
    <div className="divide-y divide-outline-variant/30 rounded-lg border border-outline-variant/30 bg-surface-container-lowest">
      <div className="flex flex-wrap items-center justify-between gap-space-md p-space-md">
        <div>
          <p className="font-label-code text-label-badge tracking-wide text-outline uppercase">
            Email
          </p>
          <div className="mt-0.5 flex flex-wrap items-center gap-space-sm">
            <span className="font-label-code text-label-code break-all text-on-surface">
              {user.email}
            </span>
            {user.is_email_verified ? (
              <VerifiedChip />
            ) : (
              <span className="inline-flex items-center gap-space-xs rounded-lg border border-outline-variant/30 bg-surface-container-low px-space-sm py-0.5 font-label-code text-label-code text-outline uppercase">
                Not verified
              </span>
            )}
          </div>
        </div>
        {!user.is_email_verified && (
          <Link href="/verify-email" className={buttonClasses({ variant: "secondary" })}>
            Verify email
          </Link>
        )}
      </div>

      {user.has_usable_password ? (
        <Row
          icon="password"
          title="Password"
          description="Changing it signs your other devices out."
          action={
            <Button variant="secondary" onClick={() => setChanging(true)}>
              Change password
            </Button>
          }
        />
      ) : (
        <Row
          icon="password"
          title="Signed in with Google"
          description="This account has no password. To also log in with one, use Forgot password."
          action={
            <Link href="/forgot-password" className={buttonClasses({ variant: "secondary" })}>
              Set a password
            </Link>
          }
        />
      )}

      {user.google_connected && (
        <Row
          icon="link"
          title="Google sign-in connected"
          description="Continue with Google opens this account."
        />
      )}

      <ChangePasswordModal open={changing} onClose={() => setChanging(false)} />
    </div>
  );
}
