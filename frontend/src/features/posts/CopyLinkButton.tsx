"use client";

import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

/** The address of a post's page, from wherever the visitor is reading it. */
export function postUrl(id: string, origin: string): string {
  return `${origin}/p/${id}`;
}

export const COPY_LINK_MESSAGES = {
  copied: "Link copied.",
  failed: "Couldn't copy the link. Copy the address from your browser's address bar instead.",
} as const;

/** "Copy link" (Part 5): the share action. Copies `window.location.origin` + `/p/{id}`. */
export function CopyLinkButton({ postId }: { postId: string }) {
  const toast = useToast();

  async function copy() {
    try {
      await navigator.clipboard.writeText(postUrl(postId, window.location.origin));
      toast.show(COPY_LINK_MESSAGES.copied, { tone: "success" });
    } catch {
      toast.show(COPY_LINK_MESSAGES.failed, { tone: "error" });
    }
  }

  return (
    <Button variant="secondary" onClick={() => void copy()}>
      <Icon name="content_copy" size="lg" />
      Copy link
    </Button>
  );
}
