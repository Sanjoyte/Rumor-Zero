import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";

/** What a feed shows while its first page loads: the shape of a PostCard, in grey blocks. */
export function PostCardSkeleton() {
  return (
    <Card aria-hidden="true" className="flex flex-col gap-space-md p-space-lg">
      <div className="flex items-center gap-space-md">
        <Skeleton className="h-10 w-10 rounded-full" />
        <Skeleton className="h-4 w-40" />
      </div>
      <Skeleton className="h-5 w-full" />
      <Skeleton className="h-5 w-2/3" />
    </Card>
  );
}
