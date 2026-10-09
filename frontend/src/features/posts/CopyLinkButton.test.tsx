import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/ui/Toast";
import { COPY_LINK_MESSAGES, CopyLinkButton, postUrl } from "./CopyLinkButton";

const ID = "11111111-1111-4111-8111-111111111111";

afterEach(() => vi.restoreAllMocks());

function renderButton() {
  return render(
    <ToastProvider>
      <CopyLinkButton postId={ID} />
    </ToastProvider>,
  );
}

describe("postUrl", () => {
  it("is the origin plus /p/{id}", () => {
    expect(postUrl(ID, "https://rumor-zero.example.workers.dev")).toBe(
      `https://rumor-zero.example.workers.dev/p/${ID}`,
    );
  });
});

describe("CopyLinkButton", () => {
  it("copies this site's address of the post and says so", async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    renderButton();
    await user.click(screen.getByRole("button", { name: "Copy link" }));
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/p/${ID}`);
    expect(await screen.findByText(COPY_LINK_MESSAGES.copied)).toBeInTheDocument();
  });

  it("tells the visitor to copy the address bar when the browser refuses", async () => {
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
    renderButton();
    await user.click(screen.getByRole("button", { name: "Copy link" }));
    expect(await screen.findByText(COPY_LINK_MESSAGES.failed)).toBeInTheDocument();
    expect(screen.queryByText(COPY_LINK_MESSAGES.copied)).toBeNull();
  });
});
