import type { Metadata } from "next";
import { Placeholder } from "@/components/shell/Placeholder";

type Props = { params: Promise<{ username: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { username } = await params;
  return { title: `@${username}` };
}

/** Placeholder; Part 6 builds the profile (Stitch c1). */
export default async function ProfilePage({ params }: Props) {
  const { username } = await params;
  return <Placeholder title={`@${username}`} />;
}
