"use client";

import { useRouter } from "next/navigation";
import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useToast } from "@/components/ui/Toast";
import { MESSAGES } from "@/features/auth/messages";
import type { FactQuota, Post } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { loginRedirectFor } from "@/lib/auth/route-guard";
import { ComposerModal, type ComposerSubmit } from "./ComposerModal";
import { type Draft, emptyDraft } from "./draft";
import { type ComposerFailure, composerFailure, POST_MESSAGES } from "./messages";
import { createPost, fetchFactQuota } from "./posts-api";

interface ComposerContextValue {
  /** Open the composer (a toast for an unverified user, the login page for a visitor). */
  open: () => void;
  /** Hear about every post the composer creates; returns the unsubscribe. */
  onPosted: (listener: (post: Post) => void) => () => void;
}

const ComposerContext = createContext<ComposerContextValue | null>(null);

export function useComposer(): ComposerContextValue {
  const value = useContext(ComposerContext);
  if (!value) throw new Error("useComposer must be used inside <ComposerProvider>");
  return value;
}

/**
 * Owns the composer: the draft, the request and the modal, so every "New post" button (rail, phone
 * tab, the `/home` card) opens the same one (ARCHITECTURE §10).
 *
 * - **Insert on success** (user decision 2026-10-08): the modal stays open showing "Posting…"; on a
 *   201 it closes, the draft is cleared, listeners get the server's post (the feed puts it at the
 *   top) and a toast says so. Errors keep the draft and stay in the composer.
 * - **The provider, not the modal, owns the request:** Esc can close the modal while the post is
 *   still on its way (the relay waits up to 70 s). The result is still handled: success clears the
 *   draft and toasts, failure keeps the draft and toasts that it's saved.
 * - The draft survives Cancel, Esc and ×, in memory only. A change of user clears it.
 */
export function ComposerProvider({
  children,
  now,
  timeZone,
}: {
  children: ReactNode;
  /** Clock and zone for "next at 14:05"; tests pass fixed ones. */
  now?: Date;
  timeZone?: string;
}) {
  const { status, user, reloadMe } = useAuth();
  const toast = useToast();
  const router = useRouter();
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<ComposerFailure | null>(null);
  const [quota, setQuota] = useState<FactQuota | null>(null);
  const listeners = useRef(new Set<(post: Post) => void>());
  const submittingRef = useRef(false);
  // Read by `submit` when its answer arrives: was the modal closed in the meantime?
  const openRef = useRef(false);
  useEffect(() => {
    openRef.current = isOpen;
  }, [isOpen]);

  // Whatever one person typed is not offered to the next one (logout, another account).
  const userId = user?.id ?? null;
  const [draftOwner, setDraftOwner] = useState(userId);
  if (draftOwner !== userId) {
    setDraftOwner(userId);
    setDraft(emptyDraft());
    setFailure(null);
    setQuota(null);
    setIsOpen(false);
  }

  const refreshQuota = useCallback(async () => {
    try {
      setQuota(await fetchFactQuota());
    } catch {
      // The line stays hidden or stale; the server still decides.
    }
  }, []);

  const open = useCallback(() => {
    if (status === "loading") return;
    if (status === "anonymous" || !user) {
      router.push(loginRedirectFor(window.location.pathname + window.location.search));
      return;
    }
    if (!user.is_email_verified) {
      toast.show(MESSAGES.newPostBlocked);
      return;
    }
    setIsOpen(true);
    void refreshQuota();
  }, [status, user, router, toast, refreshQuota]);

  const close = useCallback(() => setIsOpen(false), []);

  const onDraftChange = useCallback((patch: Partial<Draft>) => {
    setDraft((current) => ({ ...current, ...patch }));
    // A quota or paused message is about Fact: choosing the other type makes it stale.
    if (patch.postType !== undefined) setFailure(null);
  }, []);

  const submit = useCallback(
    async (payload: ComposerSubmit): Promise<ComposerFailure | null> => {
      if (submittingRef.current) return null;
      submittingRef.current = true;
      setSubmitting(true);
      setFailure(null);
      try {
        const post = await createPost({
          content: payload.content,
          post_type: payload.postType,
          ...(payload.postType === "fact" ? { sources: payload.sources } : {}),
        });
        setDraft(emptyDraft());
        close();
        listeners.current.forEach((listener) => listener(post));
        toast.show(post.post_type === "fact" ? POST_MESSAGES.postedFact : POST_MESSAGES.posted, {
          tone: "success",
        });
        if (post.post_type === "fact") void refreshQuota();
        return null;
      } catch (error) {
        const result = composerFailure(error);
        if (result.kind !== "fields") setFailure(result);
        if (result.kind === "quota" || result.kind === "paused") void refreshQuota();
        if (result.kind === "unverified") void reloadMe();
        if (!openRef.current) {
          const message = result.kind === "fields" ? POST_MESSAGES.postFailedKept : result.message;
          toast.show(message, { tone: "error" });
        }
        return result;
      } finally {
        submittingRef.current = false;
        setSubmitting(false);
      }
    },
    [close, toast, refreshQuota, reloadMe],
  );

  const onPosted = useCallback((listener: (post: Post) => void) => {
    listeners.current.add(listener);
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  const value = useMemo(() => ({ open, onPosted }), [open, onPosted]);

  return (
    <ComposerContext.Provider value={value}>
      {children}
      <ComposerModal
        open={isOpen}
        onClose={close}
        draft={draft}
        onDraftChange={onDraftChange}
        submitting={submitting}
        failure={failure}
        quota={quota}
        verified={Boolean(user?.is_email_verified)}
        onSubmit={submit}
        now={now}
        timeZone={timeZone}
      />
    </ComposerContext.Provider>
  );
}
