import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Connections } from "@/features/social/Connections";

type Props = { params: Promise<{ username: string }> };

const NAME = /^[A-Za-z0-9_]{3,30}$/;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { username } = await params;
  // A list of people adds little for search, so it is kept out of the index.
  return {
    title: `People followed by @${username.toLowerCase()}`,
    robots: { index: false, follow: true },
  };
}

/** The following list (Stitch c3). Client-rendered: it reads nothing on the server. */
export default async function FollowingPage({ params }: Props) {
  const { username } = await params;
  if (!NAME.test(username)) notFound();
  return (
    <Connections
      key={`following:${username.toLowerCase()}`}
      username={username.toLowerCase()}
      tab="following"
    />
  );
}
