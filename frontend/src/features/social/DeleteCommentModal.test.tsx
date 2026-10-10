import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DeleteCommentModal } from "./DeleteCommentModal";
import { SOCIAL_MESSAGES } from "./messages";

const api = vi.hoisted(() => ({ deleteComment: vi.fn() }));
vi.mock("./social-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./social-api")>()),
  ...api,
}));

beforeEach(() => {
  api.deleteComment.mockReset();
  api.deleteComment.mockResolvedValue(undefined);
});

function open(props: Partial<React.ComponentProps<typeof DeleteCommentModal>> = {}) {
  const onClose = vi.fn();
  const onDeleted = vi.fn();
  render(<DeleteCommentModal commentId="c1" onClose={onClose} onDeleted={onDeleted} {...props} />);
  return { onClose, onDeleted };
}

describe("DeleteCommentModal", () => {
  it("is closed without a comment", () => {
    open({ commentId: null });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("asks first, and Cancel sends nothing", async () => {
    const { onClose } = open();
    expect(await screen.findByRole("dialog", { name: "Delete this comment?" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(api.deleteComment).not.toHaveBeenCalled();
  });

  it("deletes the comment and tells the parent", async () => {
    const { onDeleted } = open();
    await userEvent.click(await screen.findByRole("button", { name: "Delete comment" }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("c1"));
    expect(api.deleteComment).toHaveBeenCalledWith("c1");
  });

  it("treats a comment that is already gone (404) as deleted", async () => {
    api.deleteComment.mockRejectedValue(
      new ApiError({ status: 404, code: "not_found", detail: "x" }),
    );
    const { onDeleted } = open();
    await userEvent.click(await screen.findByRole("button", { name: "Delete comment" }));
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith("c1"));
  });

  it.each([
    [401, SOCIAL_MESSAGES.signedOut],
    [500, SOCIAL_MESSAGES.commentDeleteFailed],
  ])("keeps the dialog open and says why on a %i", async (status, message) => {
    api.deleteComment.mockRejectedValue(new ApiError({ status, code: "x", detail: "x" }));
    const { onDeleted } = open();
    await userEvent.click(await screen.findByRole("button", { name: "Delete comment" }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(onDeleted).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Delete comment" })).toBeEnabled();
  });

  it("can't be closed while the request is on its way", async () => {
    let finish!: () => void;
    api.deleteComment.mockReturnValue(new Promise<void>((res) => (finish = res)));
    const { onClose } = open();
    await userEvent.click(await screen.findByRole("button", { name: "Delete comment" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).not.toHaveBeenCalled();
    await act(async () => finish());
  });
});
