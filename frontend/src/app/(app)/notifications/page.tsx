import type { Metadata } from "next";
import { NotificationsPage } from "@/features/notifications/NotificationsPage";

// Behind a login and private: never indexed. The page is static; the list loads on the client.
export const metadata: Metadata = {
  title: "Notifications",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <NotificationsPage />;
}
