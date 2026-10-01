import { Inter, JetBrains_Mono, Newsreader } from "next/font/google";

// Self-hosted at build time by next/font (ANALYSIS a.5). Shared by the root layout and
// global-error.tsx, which replaces the root layout when it renders.
const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains-mono",
});
const newsreader = Newsreader({
  subsets: ["latin"],
  display: "swap",
  style: ["normal", "italic"],
  axes: ["opsz"],
  variable: "--font-newsreader",
});

/** The CSS-variable classes for <html>. */
export const fontVariables = `${inter.variable} ${jetbrainsMono.variable} ${newsreader.variable}`;
