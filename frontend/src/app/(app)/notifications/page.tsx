import type { Metadata } from "next";
import { Placeholder } from "@/components/shell/Placeholder";

export const metadata: Metadata = { title: "Notifications" };

/** Placeholder; the screen arrives in a later part. */
export default function Page() {
  return <Placeholder title="Notifications" />;
}
