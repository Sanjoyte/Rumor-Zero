"use client";

import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { PasswordField } from "@/components/ui/PasswordField";
import { TextField } from "@/components/ui/TextField";
import { normalizeUsername } from "@/features/auth/useUsernameAvailability";
import { ApiError } from "@/lib/api/client";
import { settingsErrorMessage } from "./messages";
import { deleteAccount } from "./settings-api";

/**
 * Delete the account, for good. An account with a password confirms with it; a Google-only one
 * types its username. The button stays off until the field is filled (a password) or matches (the
 * username); the server decides. Modelled on DeletePostModal.
 */
export function DeleteAccountModal({
  open,
  username,
  hasPassword,
  onClose,
  onDeleted,
}: {
  open: boolean;
  username: string;
  hasPassword: boolean;
  onClose: () => void;
  /** The account is gone (204): end the session and leave. */
  onDeleted: () => void;
}) {
  const [value, setValue] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A fresh form every time it opens.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setValue("");
      setFieldError(null);
      setBanner(null);
    }
  }

  const ready = hasPassword ? value.length > 0 : normalizeUsername(value) === username;

  function close() {
    if (busy) return;
    onClose();
  }

  async function confirm(event?: FormEvent) {
    event?.preventDefault();
    if (busy || !ready) return;
    setBusy(true);
    setFieldError(null);
    setBanner(null);
    try {
      await deleteAccount(hasPassword ? { password: value } : { username: value });
      onDeleted();
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.fieldErrors[hasPassword ? "password" : "username"]?.[0]
          : undefined;
      if (message) setFieldError(message);
      else setBanner(settingsErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="Delete your account?"
      icon="delete"
      footerTone="plain"
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={busy} data-autofocus>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => void confirm()}
            loading={busy}
            disabled={!ready}
          >
            Delete account
          </Button>
        </>
      }
    >
      <form className="flex flex-col gap-space-md" noValidate onSubmit={(e) => void confirm(e)}>
        <p className="font-body-md text-body-md text-on-surface">
          This can&apos;t be undone. You are signed out everywhere at once.
        </p>
        <div className="space-y-space-xs">
          <p className="font-body-sm text-body-sm font-semibold text-on-surface">What goes</p>
          <ul className="list-disc space-y-space-xs pl-space-lg font-body-sm text-body-sm text-on-surface-variant">
            <li>
              Your profile, posts, comments, likes, follows, bookmarks, reposts, reports and
              appeals.
            </li>
            <li>Your credibility history and the notifications you received or caused.</li>
            <li>Your username, which anyone can then take.</li>
          </ul>
        </div>
        <div className="space-y-space-xs">
          <p className="font-body-sm text-body-sm font-semibold text-on-surface">What stays</p>
          <ul className="list-disc space-y-space-xs pl-space-lg font-body-sm text-body-sm text-on-surface-variant">
            <li>Moderation records keep a copy of removed posts, without your name.</li>
          </ul>
        </div>
        {banner && (
          <Alert tone="error" onDismiss={() => setBanner(null)}>
            <p className="font-medium">{banner}</p>
          </Alert>
        )}
        <fieldset disabled={busy}>
          <legend className="sr-only">Confirm</legend>
          {hasPassword ? (
            <PasswordField
              label="Your password"
              name="password"
              autoComplete="current-password"
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                setFieldError(null);
              }}
              error={fieldError ?? undefined}
              hint="Enter your password to confirm."
            />
          ) : (
            <TextField
              label="Type your username to confirm"
              name="username"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              mono
              value={value}
              onChange={(event) => {
                setValue(event.target.value);
                setFieldError(null);
              }}
              error={fieldError ?? undefined}
              hint={`Type ${username} to confirm.`}
            />
          )}
        </fieldset>
        <button type="submit" className="hidden" tabIndex={-1} aria-hidden="true" />
      </form>
    </Modal>
  );
}
