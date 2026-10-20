"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Textarea } from "@/components/ui/Textarea";
import { TextField } from "@/components/ui/TextField";
import { useToast } from "@/components/ui/Toast";
import {
  USERNAME_FORMAT_MESSAGE,
  USERNAME_PATTERN,
  normalizeUsername,
  useUsernameAvailability,
} from "@/features/auth/useUsernameAvailability";
import { ApiError } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { countCharacters } from "@/lib/format";
import { SETTINGS_MESSAGES, settingsErrorMessage } from "./messages";
import { updateProfile, type ProfileChanges } from "./settings-api";

export const MAX_DISPLAY_NAME = 50;
export const MAX_BIO = 280;

type Field = "display_name" | "username" | "bio";
type FieldErrors = Partial<Record<Field, string>>;
const FIELD_ORDER: Field[] = ["display_name", "username", "bio"];
const FIELD_IDS: Record<Field, string> = {
  display_name: "settings-display-name",
  username: "settings-username",
  bio: "settings-bio",
};

/** The bio as the server stores it: one newline style, trimmed. */
function cleanBio(value: string): string {
  return value.replace(/\r\n?/g, "\n").trim();
}

/** The form's changes against the saved profile; only changed fields are sent. */
function changesFor(user: Me, displayName: string, username: string, bio: string): ProfileChanges {
  const changes: ProfileChanges = {};
  if (displayName.trim() !== user.display_name) changes.display_name = displayName.trim();
  if (normalizeUsername(username) !== user.username) changes.username = normalizeUsername(username);
  if (cleanBio(bio) !== user.bio) changes.bio = cleanBio(bio);
  return changes;
}

function validate(changes: ProfileChanges): FieldErrors {
  const errors: FieldErrors = {};
  if (
    changes.display_name !== undefined &&
    countCharacters(changes.display_name) > MAX_DISPLAY_NAME
  ) {
    errors.display_name = `Display names are at most ${MAX_DISPLAY_NAME} characters.`;
  }
  if (changes.username !== undefined && !USERNAME_PATTERN.test(changes.username)) {
    errors.username = USERNAME_FORMAT_MESSAGE;
  }
  if (changes.bio !== undefined && countCharacters(changes.bio) > MAX_BIO) {
    errors.bio = `Bios are at most ${MAX_BIO} characters.`;
  }
  return errors;
}

/**
 * Settings, section 1 (Stitch c2 "Public Identity"): display name, username and bio. The save bar
 * appears only while something differs from the saved profile. Unverified accounts can read but not
 * edit (the server answers 403 `email_unverified`), so the fields are locked and say why.
 */
export function ProfileForm({ user }: { user: Me }) {
  const { reloadMe } = useAuth();
  const toast = useToast();
  const [displayName, setDisplayName] = useState(user.display_name);
  const [username, setUsername] = useState(user.username);
  const [bio, setBio] = useState(user.bio);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const pendingFocus = useRef<Field | null>(null);

  // The saved profile changed (saved here, or in another tab): show it. A pending edit is replaced.
  const savedKey = JSON.stringify([user.display_name, user.username, user.bio]);
  const [syncedKey, setSyncedKey] = useState(savedKey);
  if (syncedKey !== savedKey) {
    setSyncedKey(savedKey);
    setDisplayName(user.display_name);
    setUsername(user.username);
    setBio(user.bio);
  }

  const verified = user.is_email_verified;
  const changes = changesFor(user, displayName, username, bio);
  const dirty = Object.keys(changes).length > 0;
  // The live check is for a name that is not already yours.
  const availability = useUsernameAvailability(
    normalizeUsername(username) === user.username ? "" : username,
  );

  useEffect(() => {
    const field = pendingFocus.current;
    if (!field) return;
    pendingFocus.current = null;
    document.getElementById(FIELD_IDS[field])?.focus();
  }, [fieldErrors]);

  function fail(errors: FieldErrors) {
    pendingFocus.current = FIELD_ORDER.find((field) => errors[field]) ?? null;
    setFieldErrors(errors);
  }

  function reset() {
    setDisplayName(user.display_name);
    setUsername(user.username);
    setBio(user.bio);
    setFieldErrors({});
    setBanner(null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!dirty || saving) return;
    setBanner(null);
    const errors = validate(changes);
    fail(errors);
    if (Object.keys(errors).length > 0) return;

    setSaving(true);
    try {
      const saved = await updateProfile(changes);
      setDisplayName(saved.display_name);
      setUsername(saved.username);
      setBio(saved.bio);
      setFieldErrors({});
      toast.show(SETTINGS_MESSAGES.profileSaved, { tone: "success" });
      // Updates the shell (the rail and the account menu) and the other tabs.
      await reloadMe().catch(() => {});
    } catch (error) {
      const fromServer: FieldErrors = {};
      if (error instanceof ApiError) {
        for (const field of FIELD_ORDER) {
          const message = error.fieldErrors[field]?.[0];
          if (message) fromServer[field] = message;
        }
      }
      fail(fromServer);
      if (Object.keys(fromServer).length === 0) setBanner(settingsErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  const usernameError =
    fieldErrors.username ??
    (["taken", "reserved", "invalid"].includes(availability.status)
      ? (availability.message ?? undefined)
      : undefined);
  const usernameAvailable = !fieldErrors.username && availability.status === "available";
  const usernameBlocked = ["taken", "reserved", "invalid"].includes(availability.status);

  return (
    <form className="space-y-space-lg" noValidate onSubmit={(event) => void onSubmit(event)}>
      {!verified && (
        <Alert tone="info">
          <p className="font-medium">{SETTINGS_MESSAGES.unverified}</p>
          <Link href="/verify-email" className="text-secondary hover:underline">
            Check your inbox or resend the link
          </Link>
        </Alert>
      )}
      {banner && (
        <Alert tone="error" onDismiss={() => setBanner(null)}>
          <p className="font-medium">{banner}</p>
        </Alert>
      )}
      <fieldset disabled={!verified || saving} className="space-y-space-lg">
        <legend className="sr-only">Public profile</legend>
        <div className="grid grid-cols-1 gap-space-md md:grid-cols-2">
          <TextField
            id={FIELD_IDS.display_name}
            label="Display name"
            name="display_name"
            autoComplete="name"
            value={displayName}
            onChange={(event) => {
              setDisplayName(event.target.value);
              setFieldErrors((current) => ({ ...current, display_name: undefined }));
            }}
            error={fieldErrors.display_name}
            hint={`Shown next to your username. Up to ${MAX_DISPLAY_NAME} characters.`}
          />
          <TextField
            id={FIELD_IDS.username}
            label="Username"
            name="username"
            mono
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={username}
            onChange={(event) => {
              setUsername(event.target.value);
              setFieldErrors((current) => ({ ...current, username: undefined }));
            }}
            error={usernameError}
            success={usernameAvailable ? `Available: @${availability.username}` : undefined}
            hint={
              availability.status === "checking"
                ? "Checking…"
                : "Your old link stops working, and anyone can take the old name."
            }
            trailing={
              usernameAvailable ? (
                <span className="pointer-events-none text-primary">
                  <Icon name="check" />
                </span>
              ) : undefined
            }
          />
        </div>
        <Textarea
          id={FIELD_IDS.bio}
          label="Bio"
          name="bio"
          variant="filled"
          rows={3}
          maxCount={MAX_BIO}
          value={bio}
          onChange={(event) => {
            setBio(event.target.value);
            setFieldErrors((current) => ({ ...current, bio: undefined }));
          }}
          error={fieldErrors.bio}
          hint="Plain text. Shown on your profile."
        />
      </fieldset>

      {dirty && verified && (
        <div
          role="group"
          aria-label="Unsaved changes"
          className="flex flex-wrap items-center justify-between gap-space-md rounded-lg border border-secondary/30 bg-secondary/10 p-space-md"
        >
          <p className="flex items-center gap-space-sm font-body-sm text-body-sm text-on-surface-variant">
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-secondary" />
            You have unsaved changes
          </p>
          <div className="flex items-center gap-space-sm">
            <Button variant="secondary" onClick={reset} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" loading={saving} disabled={usernameBlocked}>
              <Icon name="save" size="lg" />
              Save changes
            </Button>
          </div>
        </div>
      )}
    </form>
  );
}
