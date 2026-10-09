import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DELETE_MESSAGES, DeletePostModal } from "./DeletePostModal";

const api = vi.hoisted(() => ({ deletePost: vi.fn() }));
vi.mock("./posts-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./posts-api")>()),
  ...api,
}));

const ID = "11111111-1111-4111-8111-111111111111";
let onClose: Mock<() => void>;
let onDeleted: Mock<() => void>;

beforeEach(() => {
  api.deletePost.mockReset();
  onClose = vi.fn<() => void>();
  onDeleted = vi.fn<() => void>();
});

function renderModal(isFact = false, open = true) {
  return render(
    <DeletePostModal
      open={open}
      postId={ID}
      isFact={isFact}
      onClose={onClose}
      onDeleted={onDeleted}
    />,
  );
}

describe("DeletePostModal", () => {
  it("asks first, and says it can't be undone", () => {
    renderModal();
    expect(screen.getByRole("dialog", { name: "Delete this post?" })).toBeInTheDocument();
    expect(screen.getByText(/can't be undone/)).toBeInTheDocument();
    expect(api.deletePost).not.toHaveBeenCalled();
  });

  it("warns that a deleted fact post still counts toward the allowance, an opinion doesn't", () => {
    const { unmount } = renderModal(true);
    expect(screen.getByText(/still counts toward your fact posts/)).toBeInTheDocument();
    unmount();
    renderModal(false);
    expect(screen.queryByText(/still counts/)).toBeNull();
  });

  it("deletes and reports it", async () => {
    const user = userEvent.setup();
    api.deletePost.mockResolvedValue(undefined);
    renderModal();
    await user.click(screen.getByRole("button", { name: "Delete post" }));
    expect(api.deletePost).toHaveBeenCalledWith(ID);
    await waitFor(() => expect(onDeleted).toHaveBeenCalledTimes(1));
  });

  it("is busy while the request runs and can't be closed or repeated", async () => {
    const user = userEvent.setup();
    let finish: () => void = () => {};
    api.deletePost.mockReturnValue(new Promise<void>((resolve) => (finish = resolve)));
    renderModal();
    await user.click(screen.getByRole("button", { name: "Delete post" }));
    const button = screen.getByRole("button", { name: /Delete post/ });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).not.toHaveBeenCalled();
    finish();
    await waitFor(() => expect(onDeleted).toHaveBeenCalled());
    expect(api.deletePost).toHaveBeenCalledTimes(1);
  });

  it("counts a 404 (already gone) as deleted", async () => {
    const user = userEvent.setup();
    api.deletePost.mockRejectedValue(new ApiError({ status: 404, code: "not_found", detail: "" }));
    renderModal();
    await user.click(screen.getByRole("button", { name: "Delete post" }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalledTimes(1));
  });

  it("shows an error and keeps the post for any other failure", async () => {
    const user = userEvent.setup();
    api.deletePost.mockRejectedValue(
      new ApiError({ status: 0, code: "network_error", detail: "" }),
    );
    renderModal();
    await user.click(screen.getByRole("button", { name: "Delete post" }));
    expect(await screen.findByText(DELETE_MESSAGES.failed)).toBeInTheDocument();
    expect(onDeleted).not.toHaveBeenCalled();
    // And it can be tried again.
    api.deletePost.mockResolvedValue(undefined);
    await user.click(screen.getByRole("button", { name: "Delete post" }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalledTimes(1));
  });

  it("says when the session ended", async () => {
    const user = userEvent.setup();
    api.deletePost.mockRejectedValue(
      new ApiError({ status: 401, code: "not_authenticated", detail: "" }),
    );
    renderModal();
    await user.click(screen.getByRole("button", { name: "Delete post" }));
    expect(await screen.findByText(DELETE_MESSAGES.signedOut)).toBeInTheDocument();
  });

  it("closes on Cancel and forgets the error", async () => {
    const user = userEvent.setup();
    renderModal();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(api.deletePost).not.toHaveBeenCalled();
  });
});
