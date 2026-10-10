"use client";

import { useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ApiError } from "@/lib/api/client";
import { SOCIAL_MESSAGES } from "./messages";
import { deleteComment } from "./social-api";

/**
 * The confirmation before an author deletes their comment: it leaves the list and the count at
 * once. A comment that is already gone (404) counts as deleted.
 */
export function DeleteCommentModal({
  commentId,
  onClose,
  onDeleted,
}: {
  /** The comment to delete; null keeps the dialog closed. */
  commentId: string | null;
  onClose: () => void;
  onDeleted: (commentId: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    if (!commentId) return;
    setBusy(true);
    setError(null);
    try {
      await deleteComment(commentId);
      onDeleted(commentId);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 404) onDeleted(commentId);
      else if (caught instanceof ApiError && caught.status === 401) {
        setError(SOCIAL_MESSAGES.signedOut);
      } else setError(SOCIAL_MESSAGES.commentDeleteFailed);
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
      open={commentId !== null}
      onClose={close}
      title="Delete this comment?"
      icon="delete"
      footerTone="plain"
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={busy} data-autofocus>
            Cancel
          </Button>
          <Button variant="destructive" onClick={() => void confirm()} loading={busy}>
            Delete comment
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-space-md">
        <p className="font-body-md text-body-md text-on-surface">
          It disappears from the discussion right away. This can&apos;t be undone.
        </p>
        {error && <Alert tone="error">{error}</Alert>}
      </div>
    </Modal>
  );
}
