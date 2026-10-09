import { notFound } from "next/navigation";
import { cache } from "react";
import { PostDetail } from "@/features/posts/PostDetail";
import { postMetadata } from "@/features/posts/post-metadata";
import { fetchPublicPost, type PublicPostResult } from "@/lib/api/server";

type Props = { params: Promise<{ id: string }> };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * One backend read per request, shared by `generateMetadata` and the page. Anything that isn't a
 * UUID is a 404 without asking the backend.
 */
const loadPost = cache(async (id: string): Promise<PublicPostResult> => {
  if (!UUID.test(id)) return { kind: "not-found" };
  return fetchPublicPost(id);
});

export async function generateMetadata({ params }: Props) {
  const { id } = await params;
  return postMetadata(id, await loadPost(id));
}

/**
 * A post's page (Stitch b3), with a light server render (ANALYSIS c-35): the claim and its status
 * are in the HTML for link previews and search, anonymously; the rest hydrates on the client. A
 * backend that doesn't answer in time isn't a 404: the client then fetches the post itself.
 */
export default async function PostPage({ params }: Props) {
  const { id } = await params;
  const result = await loadPost(id);
  if (result.kind === "not-found") notFound();
  return <PostDetail key={id} id={id} initial={result.kind === "found" ? result.post : null} />;
}
