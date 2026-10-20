import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { DataExportCard } from "./DataExportCard";
import { SETTINGS_MESSAGES } from "./messages";
import { renderSettings } from "./test-helpers";

const api = vi.hoisted(() => ({ fetchExport: vi.fn(), saveJsonFile: vi.fn() }));
vi.mock("./settings-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./settings-api")>()),
  ...api,
}));

beforeEach(() => {
  api.fetchExport.mockReset();
  api.saveJsonFile.mockReset();
});

const button = () => screen.getByRole("button", { name: /Download your data/ });

describe("DataExportCard", () => {
  it("lists what the file holds", () => {
    renderSettings(<DataExportCard username="ada" />);
    expect(screen.getByText(/profile, posts, comments, likes/)).toBeInTheDocument();
    expect(button()).toHaveTextContent("Download your data (JSON)");
  });

  it("downloads the export under the server's file name", async () => {
    const user = userEvent.setup();
    const data = { format: "rumor-zero-export", posts: [] };
    api.fetchExport.mockResolvedValue(data);
    renderSettings(<DataExportCard username="ada" />);
    await user.click(button());

    await waitFor(() => expect(api.saveJsonFile).toHaveBeenCalledTimes(1));
    const [saved, filename] = api.saveJsonFile.mock.calls[0];
    expect(saved).toBe(data);
    expect(filename).toMatch(/^rumor-zero-ada-\d{4}-\d{2}-\d{2}\.json$/);
  });

  it("shows a busy button while it prepares, and asks once", async () => {
    const user = userEvent.setup();
    let finish: (value: unknown) => void = () => {};
    api.fetchExport.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    renderSettings(<DataExportCard username="ada" />);
    await user.click(button());
    expect(button()).toHaveAttribute("aria-busy", "true");
    await user.click(button());
    expect(api.fetchExport).toHaveBeenCalledTimes(1);
    finish({});
    await waitFor(() => expect(button()).not.toHaveAttribute("aria-busy", "true"));
  });

  it("says so when it is throttled", async () => {
    const user = userEvent.setup();
    api.fetchExport.mockRejectedValue(
      new ApiError({ status: 429, code: "throttled", detail: "x" }),
    );
    renderSettings(<DataExportCard username="ada" />);
    await user.click(button());
    expect(await screen.findByText(SETTINGS_MESSAGES.exportThrottled)).toBeInTheDocument();
    expect(api.saveJsonFile).not.toHaveBeenCalled();
  });

  it("says so when it fails, and lets you try again", async () => {
    const user = userEvent.setup();
    api.fetchExport.mockRejectedValue(
      new ApiError({ status: 0, code: "network_error", detail: "x" }),
    );
    renderSettings(<DataExportCard username="ada" />);
    await user.click(button());
    expect(await screen.findByText(SETTINGS_MESSAGES.exportFailed)).toBeInTheDocument();
    expect(button()).toBeEnabled();
  });
});
