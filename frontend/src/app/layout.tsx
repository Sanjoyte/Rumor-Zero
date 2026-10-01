import type { Metadata } from "next";
import type { ReactNode } from "react";
import { fontVariables } from "./fonts";
import "./globals.css";
import { Providers } from "./providers";

const description =
  "Text-only posts, labelled Opinion or Fact, with facts checked before you rely on them.";

export const metadata: Metadata = {
  // Makes the file-convention Open Graph image URL absolute.
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  // Pages set their own title: "<Page> · Rumor Zero".
  title: { default: "Rumor Zero", template: "%s · Rumor Zero" },
  description,
  applicationName: "Rumor Zero",
  openGraph: { type: "website", siteName: "Rumor Zero", title: "Rumor Zero", description },
  twitter: { card: "summary_large_image", title: "Rumor Zero", description },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={fontVariables}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
