"use client";

import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Avatar } from "@/components/ui/Avatar";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { useToast } from "@/components/ui/Toast";
import type { Me } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { PHOTO_MESSAGES, photoErrorMessage } from "./messages";
import {
  ACCEPTED_TYPES,
  PhotoPrepError,
  preparePhoto,
  type PhotoProblem,
  type PreparedPhoto,
} from "./photo-prep";
import { removeAvatar, uploadAvatar } from "./settings-api";

const USE_BUTTON_ID = "photo-use";

type Phase = "idle" | "preparing" | "preview" | "uploading" | "removing";

const PROBLEM_TEXT: Record<PhotoProblem, string> = {
  type: PHOTO_MESSAGES.type,
  too_big: PHOTO_MESSAGES.tooBig,
  unreadable: PHOTO_MESSAGES.unreadable,
  too_small: PHOTO_MESSAGES.tooSmall,
};

export interface AvatarUploaderProps {
  user: Me;
  /** Turns the chosen file into the JPEG to upload. Only tests replace it. */
  prepare?: (file: File) => Promise<PreparedPhoto>;
}

/**
 * Settings, section 1, above the profile form (Stitch c2's avatar card, with its copy rewritten):
 * choose a file, see the square preview, then **Use this photo** or Cancel. The browser re-encodes
 * the file first (`photo-prep.ts`), so what is uploaded is a small square JPEG without location
 * data; the upload shows its real percentage and Cancel aborts it. Remove photo needs no
 * confirmation. A blocked account sees why instead of an upload button; an unverified one sees
 * the button disabled. Taking the photo down stays possible in both cases.
 */
export function AvatarUploader({
  user,
  prepare = (file) => preparePhoto(file),
}: AvatarUploaderProps) {
  const { reloadMe } = useAuth();
  const toast = useToast();
  const [phase, setPhase] = useState<Phase>("idle");
  const [preview, setPreview] = useState<{ blob: Blob; url: string } | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const upload = useRef<AbortController | null>(null);

  const hasPhoto = Boolean(user.avatar_url);
  const blocked = user.avatar_uploads_blocked;
  const unverified = !user.is_email_verified;
  const busy = phase !== "idle";
  const name = user.display_name || user.username;

  // The preview's object URL lives as long as the preview: revoked when it changes or goes.
  const previewUrl = preview?.url;
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // A keyboard user lands on the main button of the new step. (`Button` takes no ref.)
  useEffect(() => {
    if (phase === "preview") document.getElementById(USE_BUTTON_ID)?.focus();
  }, [phase]);

  // Leaving the page mid-upload ends the request.
  useEffect(() => () => upload.current?.abort(), []);

  async function onChoose(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Reset, so choosing the same file again (after Cancel) still fires `change`.
    event.target.value = "";
    if (!file) return;
    setError(null);
    setPhase("preparing");
    try {
      const prepared = await prepare(file);
      setPreview({ blob: prepared.blob, url: URL.createObjectURL(prepared.blob) });
      setPhase("preview");
    } catch (failure) {
      setError(
        failure instanceof PhotoPrepError
          ? PROBLEM_TEXT[failure.problem]
          : PHOTO_MESSAGES.unreadable,
      );
      setPhase("idle");
    }
  }

  function discardPreview() {
    setPreview(null);
    setProgress(0);
    setPhase("idle");
  }

  async function onUse() {
    if (!preview || phase !== "preview") return;
    const controller = new AbortController();
    upload.current = controller;
    setError(null);
    setProgress(0);
    setPhase("uploading");
    try {
      await uploadAvatar(preview.blob, { signal: controller.signal, onProgress: setProgress });
      toast.show(PHOTO_MESSAGES.saved, { tone: "success" });
      discardPreview();
      // Updates the rail, the top bar and the other tabs.
      await reloadMe().catch(() => {});
    } catch (failure) {
      if (controller.signal.aborted) {
        // Cancelled: the server may have finished first, so ask it.
        toast.show(PHOTO_MESSAGES.cancelled);
        discardPreview();
        await reloadMe().catch(() => {});
        return;
      }
      setError(photoErrorMessage(failure));
      setPhase("preview");
    } finally {
      if (upload.current === controller) upload.current = null;
    }
  }

  async function onRemove() {
    if (busy) return;
    setError(null);
    setPhase("removing");
    try {
      await removeAvatar();
      toast.show(PHOTO_MESSAGES.removed, { tone: "success" });
      await reloadMe().catch(() => {});
    } catch (failure) {
      setError(photoErrorMessage(failure));
    } finally {
      setPhase("idle");
    }
  }

  const hintId = "photo-unverified-hint";
  const showPreview = (phase === "preview" || phase === "uploading") && preview;

  return (
    <div className="flex flex-col gap-space-md rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-space-md">
      <div className="flex items-center gap-space-md">
        <Avatar size={14} name={name} src={user.avatar_url} />
        <div className="min-w-0 space-y-space-xs">
          <h3 className="font-body-sm text-body-sm font-semibold text-on-surface">
            {PHOTO_MESSAGES.title}
          </h3>
          <p className="max-w-xl font-body-sm text-body-sm text-outline">{PHOTO_MESSAGES.intro}</p>
        </div>
      </div>

      {blocked ? <Alert tone="warning">{PHOTO_MESSAGES.blocked}</Alert> : null}
      {unverified && !blocked ? (
        <p id={hintId} className="font-body-sm text-body-sm text-outline">
          {PHOTO_MESSAGES.unverified}
        </p>
      ) : null}
      {error ? <Alert tone="error">{error}</Alert> : null}

      {phase === "preparing" ? (
        <p role="status" className="font-body-sm text-body-sm text-outline">
          Preparing your photo…
        </p>
      ) : null}

      {showPreview ? (
        <div className="flex flex-wrap items-center gap-space-md">
          {/* A plain img: it is a blob: URL, which next/image can't optimise (ARCHITECTURE 10). */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview.url}
            alt="Preview of your new photo"
            width={96}
            height={96}
            className="h-24 w-24 shrink-0 rounded-lg border border-outline-variant/40 object-cover"
          />
          {phase === "uploading" ? (
            <div role="status" className="min-w-0 flex-1 space-y-space-xs">
              <ProgressBar value={progress * 100} label="Photo upload progress" />
              <p className="font-body-sm text-body-sm text-outline">
                {progress >= 1 ? "Saving…" : `Uploading… ${Math.round(progress * 100)}%`}
              </p>
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-space-sm">
            {phase === "preview" ? (
              <Button id={USE_BUTTON_ID} variant="primary" onClick={onUse}>
                Use this photo
              </Button>
            ) : null}
            <Button
              variant="ghost"
              onClick={phase === "uploading" ? () => upload.current?.abort() : discardPreview}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-space-sm">
          {blocked ? null : (
            <Button
              variant="secondary"
              disabled={busy || unverified}
              aria-describedby={unverified ? hintId : undefined}
              onClick={() => picker.current?.click()}
            >
              {hasPhoto ? "Change photo" : "Upload photo"}
            </Button>
          )}
          {hasPhoto ? (
            <Button
              variant="ghost"
              disabled={busy}
              loading={phase === "removing"}
              onClick={onRemove}
            >
              Remove photo
            </Button>
          ) : null}
        </div>
      )}

      <input
        ref={picker}
        type="file"
        accept={ACCEPTED_TYPES.join(",")}
        className="hidden"
        data-testid="photo-input"
        onChange={onChoose}
      />
    </div>
  );
}
