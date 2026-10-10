import type { Metadata } from "next";
import { BookmarkList } from "@/features/bookmarks/BookmarkList";

// Private to you: never indexed.
export const metadata: Metadata = { title: "Bookmarks", robots: { index: false } };

export default function Page() {
  return <BookmarkList />;
}
