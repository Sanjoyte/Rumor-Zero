"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Textarea";
import { VerdictStripe } from "@/components/ui/VerdictStripe";
import type { Post } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { countCharacters } from "@/lib/format";
import { appealPost, MAX_APPEAL_REASON } from "./appeals-api";
import { APPEAL_MESSAGES, appealFailure } from "./messages";

/** The post as the modal quotes it: its words, whether it is a fact, and what is being appealed. */
export type AppealedPost = Pick<Post, "id" | "content" | "post_type" | "status" | "removal_reason">;

export type AppealResult =
  { kind: "sent"; post: Post } | { kind: "already" | "not_appealable" | "gone" };

export interface AppealModalProps {
  open: boolean;
  post: AppealedPost;
  onClose: () => void;
  /**
   * The request went through (with the post as it now stands), or the server says it can't (an
   * appeal exists already, the post changed, the post is gone). The parent closes the modal and
   * says so; every other failure stays in the modal.
   */
  onDone: (result: AppealResult) => void;
}

/**
 * Ask for another look at a FALSE label or a removal (ARCHITECTURE §4; guide §8.4). One optional
 * box for the author's reasons and a note on what happens next. The form locks while the request
 * is on its way and the modal can't be closed then. The server decides everything, including which
 * kind of appeal this is (from the post's status).
 */
export function AppealModal({ open, post, onClose, onDone }: AppealModalProps) {
  const reasonId = useId();
  const refocus = useRef(false);
  // Single flight: a ref, because two clicks in one tick both see the old `sending`.
  const inFlight = useRef(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | undefined>();
  const [notice, setNotice] = useState<{ tone: "warning" | "error"; message: string } | null>(null);
  const [sending, setSending] = useState(false);

  // The box gets the focus when the dialog opens (it would pick its close button); this runs after
  // the dialog's own effect, which has already opened it.
  useEffect(() => {
    if (open) document.getElementById(reasonId)?.focus();
  }, [open, reasonId]);

  // A problem found after sending can only take the focus once the form has unlocked: a disabled
  // fieldset ignores `focus()`, and the state change hasn't rendered yet where the error arrives.
  useEffect(() => {
    if (sending || !refocus.current) return;
    refocus.current = false;
    document.getElementById(reasonId)?.focus();
  }, [sending, reasonId]);

  function close() {
    if (sending) return;
    onClose();
  }

  async function submit() {
    if (inFlight.current) return;
    const text = reason.trim();
    setNotice(null);
    if (countCharacters(text) > MAX_APPEAL_REASON) {
      setError(APPEAL_MESSAGES.reasonTooLong);
      document.getElementById(reasonId)?.focus();
      return;
    }
    setError(undefined);
    inFlight.current = true;
    setSending(true);
    try {
      const updated = await appealPost(post.id, { reason: text });
      onDone({ kind: "sent", post: updated });
    } catch (caught) {
      const failure = appealFailure(caught);
      if (
        failure.kind === "already" ||
        failure.kind === "not_appealable" ||
        failure.kind === "gone"
      ) {
        onDone({ kind: failure.kind });
      } else if (failure.kind === "fields") {
        setError(failure.fields.reason);
        refocus.current = true;
      } else {
        setNotice({
          tone: failure.message === APPEAL_MESSAGES.verifyInModal ? "warning" : "error",
          message: failure.message,
        });
      }
    } finally {
      inFlight.current = false;
      setSending(false);
    }
  }

  const isFact = post.post_type === "fact";
  const removal = post.status === "removed";
  const given = post.removal_reason.trim();
  const footer = (
    <div className="flex w-full flex-wrap items-center justify-end gap-space-md">
      <Button variant="ghost" onClick={close} disabled={sending}>
        Cancel
      </Button>
      <Button onClick={() => void submit()} loading={sending}>
        Send request
      </Button>
    </div>
  );

  return (
    <Modal
      open={open}
      onClose={close}
      title="Request another look"
      eyebrow="Appeal"
      icon="gavel"
      footerTone="plain"
      footer={open ? footer : null}
    >
      {open && (
        <>
          {notice && <Alert tone={notice.tone}>{notice.message}</Alert>}
          <fieldset disabled={sending} className="m-0 min-w-0 space-y-space-lg border-0 p-0">
            <div className="relative overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-low p-space-md pl-space-lg">
              <VerdictStripe tone={removal ? "outline-variant" : "error"} />
              <p
                className={cn(
                  "line-clamp-3 text-body-sm leading-relaxed break-words whitespace-pre-wrap text-on-surface-variant",
                  isFact ? "font-claim-headline" : "font-claim-opinion italic",
                )}
              >
                {"“"}
                {post.content}
                {"”"}
              </p>
            </div>
            <p className="flex items-start gap-space-xs font-body-sm text-body-sm text-on-surface">
              <Icon name={removal ? "block" : "gavel"} size="md" className="mt-0.5 shrink-0" />
              <span>
                {removal ? "A moderator removed your post." : "Your post is labelled FALSE."}
                {removal && given && (
                  <>
                    {" "}
                    <span className="text-on-surface-variant">Reason given: {given}</span>
                  </>
                )}
              </span>
            </p>
            <Textarea
              id={reasonId}
              label="Why should we look again?"
              hint="Optional."
              maxCount={MAX_APPEAL_REASON}
              value={reason}
              error={error}
              onChange={(event) => {
                setReason(event.target.value);
                setError(undefined);
              }}
            />
          </fieldset>
          <Alert tone="info" title="What happens next">
            A moderator who didn&apos;t make the first decision looks again.{" "}
            {removal
              ? "The post stays hidden meanwhile."
              : "The post shows UNDER REVIEW meanwhile."}{" "}
            You can ask once for each post.
          </Alert>
        </>
      )}
    </Modal>
  );
}
