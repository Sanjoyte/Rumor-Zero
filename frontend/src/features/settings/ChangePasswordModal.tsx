"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { PasswordField } from "@/components/ui/PasswordField";
import { PasswordStrengthMeter } from "@/components/ui/PasswordStrengthMeter";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { scorePassword } from "@/lib/password-strength";
import { SETTINGS_MESSAGES, settingsErrorMessage } from "./messages";
import { changePassword } from "./settings-api";

/** Django's MinimumLengthValidator; the other validators run on the server. */
export const MIN_PASSWORD_LENGTH = 8;

type Field = "current_password" | "new_password" | "confirm";
type FieldErrors = Partial<Record<Field, string>>;
const FIELD_ORDER: Field[] = ["current_password", "new_password", "confirm"];
const FIELD_IDS: Record<Field, string> = {
  current_password: "settings-current-password",
  new_password: "settings-new-password",
  confirm: "settings-confirm-password",
};

function validate(current: string, next: string, confirm: string): FieldErrors {
  const errors: FieldErrors = {};
  if (!current) errors.current_password = "Enter your current password.";
  if (next.length < MIN_PASSWORD_LENGTH) {
    errors.new_password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (next !== confirm) errors.confirm = "The two passwords don't match.";
  return errors;
}

/**
 * Change your password: current, new and a confirmation. The server checks the current one and the
 * strength rules; success keeps this device signed in and ends the others at their next refresh.
 */
export function ChangePasswordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [banner, setBanner] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const pendingFocus = useRef<Field | null>(null);

  // A fresh form every time it opens.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setCurrent("");
      setNext("");
      setConfirm("");
      setFieldErrors({});
      setBanner(null);
    }
  }

  // A disabled fieldset ignores focus(), so a problem takes the focus once the form unlocked.
  useEffect(() => {
    const field = pendingFocus.current;
    if (busy || !field) return;
    pendingFocus.current = null;
    document.getElementById(FIELD_IDS[field])?.focus();
  }, [busy, fieldErrors]);

  function fail(errors: FieldErrors) {
    pendingFocus.current = FIELD_ORDER.find((field) => errors[field]) ?? null;
    setFieldErrors(errors);
  }

  function close() {
    if (busy) return;
    onClose();
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (busy) return;
    setBanner(null);
    const errors = validate(current, next, confirm);
    fail(errors);
    if (Object.keys(errors).length > 0) return;

    setBusy(true);
    try {
      await changePassword(current, next);
      toast.show(SETTINGS_MESSAGES.passwordChanged, { tone: "success" });
      onClose();
    } catch (error) {
      const fromServer: FieldErrors = {};
      if (error instanceof ApiError) {
        const wrong = error.fieldErrors.current_password?.[0];
        const weak = error.fieldErrors.new_password?.[0];
        if (wrong) fromServer.current_password = wrong;
        if (weak) fromServer.new_password = weak;
      }
      fail(fromServer);
      if (Object.keys(fromServer).length === 0) setBanner(settingsErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="Change password"
      icon="password"
      footerTone="plain"
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void submit()} loading={busy}>
            Change password
          </Button>
        </>
      }
    >
      <form className="space-y-space-md" noValidate onSubmit={(event) => void submit(event)}>
        {banner && (
          <Alert tone="error" onDismiss={() => setBanner(null)}>
            <p className="font-medium">{banner}</p>
          </Alert>
        )}
        <fieldset disabled={busy} className="space-y-space-md">
          <legend className="sr-only">Change your password</legend>
          <PasswordField
            id={FIELD_IDS.current_password}
            label="Current password"
            name="current_password"
            autoComplete="current-password"
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
            error={fieldErrors.current_password}
            data-autofocus
          />
          <div>
            <PasswordField
              id={FIELD_IDS.new_password}
              label="New password"
              name="new_password"
              autoComplete="new-password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              error={fieldErrors.new_password}
            />
            <PasswordStrengthMeter score={scorePassword(next)} />
          </div>
          <PasswordField
            id={FIELD_IDS.confirm}
            label="Confirm new password"
            name="confirm_password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            error={fieldErrors.confirm}
          />
        </fieldset>
        <p className="font-body-sm text-body-sm text-outline">
          Your other devices are signed out. This one stays signed in.
        </p>
        {/* Enter submits from any field. */}
        <button type="submit" className="hidden" tabIndex={-1} aria-hidden="true" />
      </form>
    </Modal>
  );
}
