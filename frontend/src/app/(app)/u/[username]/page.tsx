import { notFound, redirect } from "next/navigation";
import { cache } from "react";
import { ProfilePage } from "@/features/social/ProfilePage";
import { profileMetadata } from "@/features/social/profile-metadata";
import { fetchPublicProfile, type PublicProfileResult } from "@/lib/api/server";

type Props = { params: Promise<{ username: string }> };

/** What a username can look like in a URL (the backend lower-cases it; stored names are ASCII). */
const NAME = /^[A-Za-z0-9_]{3,30}$/;

/**
 * One backend read per request, shared by `generateMetadata` and the page. A name that can't be a
 * username is a 404 without asking the backend.
 */
const loadProfile = cache(async (username: string): Promise<PublicProfileResult> => {
  if (!NAME.test(username)) return { kind: "not-found" };
  return fetchPublicProfile(username);
});

export async function generateMetadata({ params }: Props) {
  const { username } = await params;
  return profileMetadata(username, await loadProfile(username));
}

/**
 * A profile (Stitch c1) with a light server render (ARCHITECTURE §1): the header and the metadata
 * are in the HTML for link previews and search, anonymously; the posts and the personal parts load
 * on the client. `/u/Ada` goes to `/u/ada`. A backend that doesn't answer in time isn't a 404: the
 * client then fetches the profile itself.
 */
export default async function ProfileRoute({ params }: Props) {
  const { username } = await params;
  const result = await loadProfile(username);
  if (result.kind === "not-found") notFound();
  if (result.kind === "found" && result.profile.username !== username) {
    redirect(`/u/${result.profile.username}`);
  }
  const name = result.kind === "found" ? result.profile.username : username.toLowerCase();
  return (
    <ProfilePage
      key={name}
      username={name}
      initial={result.kind === "found" ? result.profile : null}
    />
  );
}
