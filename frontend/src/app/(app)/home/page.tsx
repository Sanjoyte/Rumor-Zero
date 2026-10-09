import type { Metadata } from "next";
import { HomeFeed } from "@/features/posts/HomeFeed";

export const metadata: Metadata = { title: "Home" };

/** Stitch b1: the composer trigger and the public Recent feed (Part 4). Following is Part 6. */
export default function Page() {
  return <HomeFeed />;
}
