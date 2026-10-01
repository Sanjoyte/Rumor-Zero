import Link from "next/link";
import { AppShell } from "@/components/shell/AppShell";
import type { ShellUser } from "@/components/shell/nav-items";
import { PostCard } from "@/features/posts/PostCard";

/** A made-up account for the preview only (never seed data). */
const SAMPLE_USER: ShellUser = {
  username: "ada",
  display_name: "Ada Lovelace",
  avatar_url: null,
  admin_url: "http://localhost:8000/admin/",
};

const NOW = new Date("2026-10-01T12:00:00Z");

/** `/dev/shell`: the app shell around sample content, logged in or out. */
export function ShellPreview({ loggedIn, activePath }: { loggedIn: boolean; activePath: string }) {
  return (
    <AppShell user={loggedIn ? SAMPLE_USER : null} activePath={activePath}>
      <div className="mx-auto flex w-full max-w-reading flex-col gap-space-lg px-margin-mobile py-space-xl md:px-space-lg">
        <div className="flex flex-col gap-space-xs">
          <h1 className="font-headline-lg text-headline-lg text-on-surface">Shell preview</h1>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            {loggedIn ? "Logged in as a sample user. " : "Logged out. "}
            <Link
              className="text-secondary hover:underline"
              href={loggedIn ? "/dev/shell?user=none" : "/dev/shell"}
            >
              {loggedIn ? "Show the logged-out shell" : "Show the logged-in shell"}
            </Link>
          </p>
        </div>
        <PostCard
          author={{ displayName: "Ada Lovelace", username: "ada" }}
          content="The sample text of a fact post that the pipeline verified."
          postType="fact"
          status="verified_true"
          verdictSource="pipeline"
          confidenceScore="94.00"
          createdAt="2026-10-01T10:00:00Z"
          now={NOW}
        />
        <PostCard
          author={{ displayName: "Grace Hopper", username: "grace" }}
          content="An opinion publishes straight away and is never fact-checked."
          postType="opinion"
          status="published"
          createdAt="2026-10-01T09:30:00Z"
          now={NOW}
        />
      </div>
    </AppShell>
  );
}
