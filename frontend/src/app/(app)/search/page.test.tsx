import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { testSession } from "@/features/auth/test-helpers";
import Page, { metadata } from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/search",
  useSearchParams: () => new URLSearchParams(""),
}));

describe("/search", () => {
  it("has a fixed title and asks search engines not to index results", () => {
    expect(metadata.title).toBe("Search");
    expect(metadata.robots).toEqual({ index: false, follow: true });
  });

  it("sets no page-level share tags, so nothing replaces the root's", () => {
    expect(metadata.openGraph).toBeUndefined();
    expect(metadata.twitter).toBeUndefined();
  });

  it("is a static page: it takes no searchParams (the client reads the address)", () => {
    expect(Page.length).toBe(0);
  });

  it("renders the search screen", async () => {
    render(
      <AuthProvider session={testSession({}, { loggedIn: false }).session}>
        <ToastProvider>
          <Page />
        </ToastProvider>
      </AuthProvider>,
    );
    expect(await screen.findByText("Search Rumor Zero")).toBeInTheDocument();
  });
});
