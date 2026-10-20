import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import {
  changePassword,
  deleteAccount,
  exportFilename,
  fetchExport,
  saveJsonFile,
  updateProfile,
} from "./settings-api";

const fetchMock = vi.fn<typeof fetch>();

function reply(status: number, body?: unknown) {
  fetchMock.mockResolvedValueOnce(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: body === undefined ? {} : { "content-type": "application/json" },
    }),
  );
}

function lastCall() {
  const [url, init] = fetchMock.mock.calls.at(-1)!;
  const headers = new Headers(init?.headers);
  return { url, method: init?.method, body: init?.body, headers };
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("settings-api", () => {
  it("PATCHes the changed profile fields as JSON and returns the new user", async () => {
    reply(200, { id: "u-1", username: "new_name" });
    const me = await updateProfile({ username: "new_name" });
    expect(me.username).toBe("new_name");
    const call = lastCall();
    expect([call.url, call.method]).toEqual(["/api/v1/me/", "PATCH"]);
    expect(JSON.parse(call.body as string)).toEqual({ username: "new_name" });
    expect(call.headers.get("X-Requested-With")).toBe("rumor-zero");
  });

  it("POSTs the passwords under the names the server expects", async () => {
    reply(204);
    await changePassword("old", "new");
    const call = lastCall();
    expect([call.url, call.method]).toEqual(["/api/v1/me/password/", "POST"]);
    expect(JSON.parse(call.body as string)).toEqual({
      current_password: "old",
      new_password: "new",
    });
  });

  it("DELETEs the account with the confirmation in the body", async () => {
    reply(204);
    await deleteAccount({ password: "pw" });
    reply(204);
    await deleteAccount({ username: "ada" });
    const [first, second] = fetchMock.mock.calls;
    expect([first[0], first[1]?.method]).toEqual(["/api/v1/me/", "DELETE"]);
    expect(JSON.parse(first[1]?.body as string)).toEqual({ password: "pw" });
    expect(JSON.parse(second[1]?.body as string)).toEqual({ username: "ada" });
  });

  it("turns a refusal into an ApiError with its code", async () => {
    reply(403, { detail: "Staff accounts can't delete themselves.", code: "staff_account" });
    await expect(deleteAccount({ password: "pw" })).rejects.toMatchObject({
      status: 403,
      code: "staff_account",
    });
    reply(400, { password: ["That password is not right."] });
    const error = await deleteAccount({ password: "no" }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).fieldErrors.password).toEqual(["That password is not right."]);
  });

  it("GETs the export", async () => {
    reply(200, { format: "rumor-zero-export" });
    expect(await fetchExport()).toEqual({ format: "rumor-zero-export" });
    expect(lastCall().url).toBe("/api/v1/me/export/");
  });

  it("names the file after the username and the UTC date", () => {
    expect(exportFilename("ada", new Date("2026-10-21T23:59:59Z"))).toBe(
      "rumor-zero-ada-2026-10-21.json",
    );
  });

  it("saves JSON as a download and revokes the object URL", () => {
    vi.useFakeTimers();
    const create = vi.fn(() => "blob:test");
    const revoke = vi.fn();
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      expect(this.download).toBe("file.json");
      expect(this.href).toBe("blob:test");
    });
    saveJsonFile({ a: 1 }, "file.json");

    expect(click).toHaveBeenCalledTimes(1);
    expect(document.querySelector("a[download]")).toBeNull(); // the link is removed again
    const blob = (create.mock.calls[0] as unknown as [Blob])[0];
    expect(blob.type).toBe("application/json");
    expect(revoke).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith("blob:test");
    click.mockRestore();
    vi.useRealTimers();
  });
});
