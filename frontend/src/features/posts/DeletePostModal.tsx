"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ApiError } from "@/lib/api/client";
import { deletePost } from "./posts-api";

export const DELETE_MESSAGES = {
  failed: "Couldn't delete the post. Check your connection and try again.",
  signedOut: "You were signed out. Log in again to delete the post.",
} as const;

/**
 * The confirmation before an author deletes their post (D6): it disappears from feeds and its page
 * at once, with no undo, and a fact post still counts toward the 24-hour allowance. A post that is
 * already gone (404) counts as deleted.
 */
export function DeletePostModal({
  open,
  postId,
  isFact,
  onClose,
  onDeleted,
}: {
  open: boolean;
  postId: string;
  isFact: boolean;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await deletePost(postId);
      onDeleted();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) {
        onDeleted();
      } else if (caught instanceof ApiError && caught.status === 401) {
        setError(DELETE_MESSAGES.signedOut);
      } else {
        setError(DELETE_MESSAGES.failed);
      }
    } finally {
      setBusy(false);
    }
  }

  function close() {
    if (busy) return;
    setError(null);
    onClose();
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="Delete this post?"
      icon="delete"
      footerTone="plain"
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={busy} data-autofocus>
            Cancel
          </Button>
          <Button variant="destructive" onClick={() => void confirm()} loading={busy}>
            Delete post
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-space-md">
        <p className="font-body-md text-body-md text-on-surface">
          It disappears from feeds and from its page right away. This can&apos;t be undone.
        </p>
        {isFact && (
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            A deleted fact post still counts toward your fact posts for the last 24 hours.
          </p>
        )}
        {error && <Alert tone="error">{error}</Alert>}
      </div>
    </Modal>
  );
}
