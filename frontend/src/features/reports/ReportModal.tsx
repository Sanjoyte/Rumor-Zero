"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { RadioCardGroup } from "@/components/ui/RadioCard";
import { Textarea } from "@/components/ui/Textarea";
import { VerdictStripe } from "@/components/ui/VerdictStripe";
import type { Post } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { countCharacters } from "@/lib/format";
import { REPORT_MESSAGES, reportFailure } from "./messages";
import { isReportReason, MAX_DETAILS, REPORT_REASONS, type ReportReason } from "./reasons";
import { reportPost } from "./reports-api";

/** The post as the modal quotes it: who wrote it, what it says, and whether it is a fact. */
export type ReportedPost = Pick<Post, "id" | "content" | "post_type"> & {
  author: Pick<Post["author"], "id" | "username" | "display_name">;
};

export type ReportOutcome = "sent" | "already" | "gone";

export interface ReportModalProps {
  open: boolean;
  post: ReportedPost;
  onClose: () => void;
  /**
   * The report went through, the server says this person already reported it, or the post is
   * gone. The parent closes the modal and says so; every other failure stays in the modal.
   */
  onDone: (outcome: ReportOutcome) => void;
}

interface Errors {
  reason?: string;
  details?: string;
}

function focusFirstProblem(problems: Errors, reasons: HTMLElement | null, detailsId: string) {
  if (problems.reason) reasons?.querySelector<HTMLElement>("input[type='radio']")?.focus();
  else if (problems.details) document.getElementById(detailsId)?.focus();
}

/**
 * Report a post (Stitch d1; ARCHITECTURE §5): why, an optional explanation (required for
 * "Something else") and a note on what happens next. No reason is chosen to start with: d1
 * preselects the first one, and a default would bias what people report. The form locks while the
 * request is on its way and the modal can't be closed then. The server decides everything; the
 * answer never says whether this report sent the post to review.
 */
export function ReportModal({ open, post, onClose, onDone }: ReportModalProps) {
  const detailsId = useId();
  const reasonsRef = useRef<HTMLDivElement>(null);
  const refocus = useRef<Errors | null>(null);
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [details, setDetails] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [notice, setNotice] = useState<{ tone: "warning" | "error"; message: string } | null>(null);
  const [sending, setSending] = useState(false);

  // The first radio gets the focus when it opens (the dialog would pick its close button); this
  // runs after the dialog's own effect, which has already opened it.
  useEffect(() => {
    if (open) reasonsRef.current?.querySelector<HTMLElement>("input[type='radio']")?.focus();
  }, [open]);

  // A problem found after sending can only take the focus once the form has unlocked: a disabled
  // fieldset ignores `focus()`, and the state change hasn't rendered yet where the error arrives.
  useEffect(() => {
    if (sending || !refocus.current) return;
    const problems = refocus.current;
    refocus.current = null;
    focusFirstProblem(problems, reasonsRef.current, detailsId);
  }, [sending, detailsId]);

  function close() {
    if (sending) return;
    onClose();
  }

  function choose(value: string) {
    if (!isReportReason(value)) return;
    setReason(value);
    setErrors((current) => ({ ...current, reason: undefined }));
  }

  async function submit() {
    if (sending) return;
    const chosen = reason;
    const text = details.trim();
    const problems: Errors = {};
    if (!chosen) problems.reason = REPORT_MESSAGES.chooseReason;
    if (chosen === "other" && !text) problems.details = REPORT_MESSAGES.detailsRequired;
    else if (countCharacters(text) > MAX_DETAILS) problems.details = REPORT_MESSAGES.detailsTooLong;
    setErrors(problems);
    setNotice(null);
    if (!chosen || problems.details) {
      return focusFirstProblem(problems, reasonsRef.current, detailsId);
    }
    setSending(true);
    try {
      await reportPost(post.id, { reason: chosen, details: text });
      onDone("sent");
    } catch (caught) {
      const failure = reportFailure(caught);
      if (failure.kind === "already") onDone("already");
      else if (failure.kind === "gone") onDone("gone");
      else if (failure.kind === "fields") {
        setErrors(failure.fields);
        refocus.current = failure.fields;
      } else {
        setNotice({
          tone: failure.message === REPORT_MESSAGES.verifyInModal ? "warning" : "error",
          message: failure.message,
        });
      }
    } finally {
      setSending(false);
    }
  }

  const isFact = post.post_type === "fact";
  const name = post.author.display_name;
  const footer = (
    <div className="flex w-full flex-wrap items-center justify-between gap-space-sm">
      <p className="flex max-w-xs items-center gap-space-sm font-body-sm text-body-sm leading-tight text-outline">
        <Icon name="fingerprint" className="shrink-0" />
        Reports are private. The author is never told who reported.
      </p>
      <div className="flex shrink-0 items-center gap-space-md">
        <Button variant="ghost" onClick={close} disabled={sending}>
          Cancel
        </Button>
        <Button onClick={() => void submit()} loading={sending}>
          Submit report
        </Button>
      </div>
    </div>
  );

  return (
    <Modal
      open={open}
      onClose={close}
      title="Report this post"
      eyebrow="Report"
      icon="flag"
      footerTone="plain"
      footer={open ? footer : null}
    >
      {open && (
        <>
          {notice && <Alert tone={notice.tone}>{notice.message}</Alert>}
          <fieldset disabled={sending} className="m-0 min-w-0 space-y-space-lg border-0 p-0">
            <div className="relative overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-low p-space-md pl-space-lg">
              <VerdictStripe tone="inverse-surface" />
              <p className="mb-space-xs font-body-sm text-body-sm font-medium text-on-surface">
                {name && `${name} `}
                <span className="font-label-code text-label-badge text-outline">
                  @{post.author.username}
                </span>
              </p>
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
            <div ref={reasonsRef} className="space-y-space-xs">
              <RadioCardGroup
                name="report-reason"
                legend="Why are you reporting this post?"
                options={REPORT_REASONS}
                value={reason}
                onChange={choose}
              />
              {errors.reason && (
                <p role="alert" className="font-body-sm text-body-sm text-error">
                  {errors.reason}
                </p>
              )}
            </div>
            <Textarea
              id={detailsId}
              label="Details"
              hint={reason === "other" ? "Required for “Something else”." : "Optional."}
              maxCount={MAX_DETAILS}
              value={details}
              error={errors.details}
              onChange={(event) => {
                setDetails(event.target.value);
                setErrors((current) => ({ ...current, details: undefined }));
              }}
            />
          </fieldset>
          <Alert tone="info" title="What happens next">
            When several people report a post, a moderator reviews it. The post stays visible
            meanwhile, and nothing is removed automatically.
          </Alert>
        </>
      )}
    </Modal>
  );
}
