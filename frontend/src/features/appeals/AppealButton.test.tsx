import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";
import {
  makePost,
  renderWithSessionAndToast,
  type SessionKind,
} from "@/features/posts/test-helpers";
import type { Post } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";
import { AppealButton, type AppealButtonProps } from "./AppealButton";
import { APPEAL_MESSAGES } from "./messages";

const api = vi.hoisted(() => ({ appealPost: vi.fn() }));
vi.mock("./appeals-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./appeals-api")>()),
  ...api,
}));

const POST: AppealButtonProps["post"] = {
  id: "p1",
  content: "Rain is nice",
  post_type: "fact",
  status: "verified_false",
  removal_reason: "",
  is_mine: true,
  can_appeal: true,
};
const FILED = makePost({ status: "under_review", appeal_status: "open", can_appeal: false });

let onFiled: Mock<(post: Post) => void>;
let onStale: Mock<() => void>;

beforeEach(() => {
  api.appealPost.mockReset();
  api.appealPost.mockResolvedValue(FILED);
  onFiled = vi.fn<(post: Post) => void>();
  onStale = vi.fn<() => void>();
});

function renderButton(
  kind: SessionKind = "verified",
  post: Partial<AppealButtonProps["post"]> = {},
) {
  return renderWithSessionAndToast(
    <AppealButton post={{ ...POST, ...post }} onFiled={onFiled} onStale={onStale} />,
    kind,
  );
}

const open = async (user: ReturnType<typeof userEvent.setup>) =>
  user.click(await screen.findByRole("button", { name: "Request another look" }));

describe("AppealButton", () => {
  it("renders nothing unless it is your post and the server says it can be appealed", async () => {
    for (const post of [{ is_mine: false }, { can_appeal: false }]) {
      const view = renderButton("verified", post);
      await waitFor(() => expect(screen.queryByRole("button")).not.toBeInTheDocument());
      expect(screen.queryByText("Request another look")).not.toBeInTheDocument();
      view.unmount();
    }
  });

  it("renders nothing for a visitor and while the session is loading", () => {
    renderButton("anonymous");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders nothing while the session is loading", () => {
    renderButton("loading");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("is a button named 'Request another look' that builds no dialog until it is clicked", async () => {
    renderButton();
    const button = await screen.findByRole("button", { name: "Request another look" });
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(button).toHaveClass("ml-auto");
    expect(document.querySelector("dialog")).toBeNull();
  });

  it("opens the dialog on a click", async () => {
    const user = userEvent.setup();
    renderButton();
    await open(user);
    expect(screen.getByRole("dialog", { name: "Request another look" })).toBeInTheDocument();
    expect(api.appealPost).not.toHaveBeenCalled();
  });

  it("is aria-disabled for an unverified email, explains itself and opens nothing", async () => {
    const user = userEvent.setup();
    renderButton("unverified");
    const button = await screen.findByRole("button", { name: "Request another look" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription(APPEAL_MESSAGES.verifyHint);
    await user.click(button);
    expect(await screen.findByText(APPEAL_MESSAGES.verifyToast)).toBeInTheDocument();
    expect(document.querySelector("dialog")).toBeNull();
    expect(api.appealPost).not.toHaveBeenCalled();
  });

  it("sends the request, closes, thanks the person and hands the post to the caller", async () => {
    const user = userEvent.setup();
    renderButton();
    await open(user);
    await user.type(screen.getByRole("textbox"), "Read it again");
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText(APPEAL_MESSAGES.sent)).toBeInTheDocument();
    expect(api.appealPost).toHaveBeenCalledWith("p1", { reason: "Read it again" });
    expect(onFiled).toHaveBeenCalledWith(FILED);
    expect(onStale).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: "Request another look" })).not.toBeInTheDocument();
  });

  it("keeps the modal it built: opening it again shows the same words", async () => {
    const user = userEvent.setup();
    renderButton();
    await open(user);
    await user.type(screen.getByRole("textbox"), "half written");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await open(user);
    expect(screen.getByRole("textbox")).toHaveValue("half written");
  });

  it("is one button throughout, so the focus can come back to it", async () => {
    const user = userEvent.setup();
    renderButton();
    const before = await screen.findByRole("button", { name: "Request another look" });
    await open(user);
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("button", { name: "Request another look" })).toBe(before);
  });

  it.each([
    ["409 already_appealed", { status: 409, code: "already_appealed" }, APPEAL_MESSAGES.already],
    ["409 not_appealable", { status: 409, code: "not_appealable" }, APPEAL_MESSAGES.notAppealable],
    ["404", { status: 404, code: "not_found" }, APPEAL_MESSAGES.gone],
  ])("on a %s it says so, closes and asks the caller to refetch", async (_, init, message) => {
    const user = userEvent.setup();
    api.appealPost.mockRejectedValue(new ApiError({ ...init, detail: "" }));
    renderButton();
    await open(user);
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(onStale).toHaveBeenCalledTimes(1);
    expect(onFiled).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog", { name: "Request another look" })).not.toBeInTheDocument();
  });
});
