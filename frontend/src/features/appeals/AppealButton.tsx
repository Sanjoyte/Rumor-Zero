"use client";

import { useId, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import type { Post } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { cn } from "@/lib/cn";
import { AppealModal, type AppealedPost, type AppealResult } from "./AppealModal";
import { APPEAL_MESSAGES } from "./messages";

export interface AppealButtonProps {
  post: AppealedPost & Pick<Post, "is_mine" | "can_appeal">;
  /** The request went through: the post as it now stands (with `appeal_status: "open"`). */
  onFiled: (post: Post) => void;
  /**
   * The server says this post can't be appealed (an appeal exists already, it changed, it is
   * gone): the caller refetches the post, so the page shows the truth.
   */
  onStale?: () => void;
  className?: string;
}

const TOASTS: Record<Exclude<AppealResult["kind"], "sent">, string> = {
  already: APPEAL_MESSAGES.already,
  not_appealable: APPEAL_MESSAGES.notAppealable,
  gone: APPEAL_MESSAGES.gone,
};

// Stitch b3's button, "REQUEST ANOTHER LOOK / APPEAL VERDICT" cut to its first half.
const CLASSES =
  "ml-auto rounded-lg bg-surface-container-high px-space-md py-space-sm font-label-code text-label-code font-semibold tracking-wider text-on-surface uppercase transition-colors hover:bg-surface-container-highest focus-visible:ring-2 focus-visible:ring-secondary/30 focus-visible:outline-none";

/**
 * "Request another look" (Stitch b3): shown only to the author of a post that can be appealed
 * (`is_mine && can_appeal`, both from the server), so a caller renders it without checking. It
 * opens `AppealModal`, built on the first click and then kept. An unverified email gets an
 * `aria-disabled` button that explains itself (Part 2's rule). One `<button>` throughout.
 */
export function AppealButton({ post, onFiled, onStale, className }: AppealButtonProps) {
  const { status, user } = useAuth();
  const toast = useToast();
  const hintId = useId();
  const [open, setOpen] = useState(false);
  const [built, setBuilt] = useState(false);

  if (!post.is_mine || !post.can_appeal || !user || status === "loading") return null;

  const unverified = !user.is_email_verified;

  function handleClick() {
    if (unverified) return toast.show(APPEAL_MESSAGES.verifyToast);
    setBuilt(true);
    setOpen(true);
  }

  function done(result: AppealResult) {
    setOpen(false);
    if (result.kind === "sent") {
      toast.show(APPEAL_MESSAGES.sent, { tone: "success" });
      onFiled(result.post);
      return;
    }
    toast.show(TOASTS[result.kind]);
    onStale?.();
  }

  return (
    <>
      <button
        type="button"
        aria-disabled={unverified || undefined}
        aria-describedby={unverified ? hintId : undefined}
        title={unverified ? APPEAL_MESSAGES.verifyHint : undefined}
        onClick={handleClick}
        className={cn(CLASSES, unverified && "cursor-not-allowed opacity-60", className)}
      >
        Request another look
      </button>
      {unverified && (
        <span id={hintId} className="sr-only">
          {APPEAL_MESSAGES.verifyHint}
        </span>
      )}
      {built && (
        <AppealModal open={open} post={post} onClose={() => setOpen(false)} onDone={done} />
      )}
    </>
  );
}
