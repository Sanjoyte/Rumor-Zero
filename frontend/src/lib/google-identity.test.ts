import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  GSI_SCRIPT_URL,
  initializeGoogleIdentity,
  loadGoogleIdentity,
  releaseGoogleHandler,
  resetGoogleIdentityForTests,
  type GoogleIdentityApi,
} from "./google-identity";

function fakeApi() {
  return { initialize: vi.fn(), renderButton: vi.fn() } satisfies GoogleIdentityApi;
}

beforeEach(() => {
  resetGoogleIdentityForTests();
});

afterEach(() => {
  delete window.google;
  document.head.querySelectorAll("script").forEach((script) => script.remove());
});

describe("loadGoogleIdentity", () => {
  it("injects Google's script once, from its own URL", async () => {
    const first = loadGoogleIdentity();
    const second = loadGoogleIdentity();
    const scripts = document.head.querySelectorAll("script");
    expect(scripts).toHaveLength(1);
    expect(scripts[0].src).toBe(GSI_SCRIPT_URL);
    expect(GSI_SCRIPT_URL).toBe("https://accounts.google.com/gsi/client");
    const api = fakeApi();
    window.google = { accounts: { id: api } };
    scripts[0].dispatchEvent(new Event("load"));
    expect(await first).toBe(api);
    expect(await second).toBe(api);
  });

  it("adds no script when Google's is already there", async () => {
    const api = fakeApi();
    window.google = { accounts: { id: api } };
    expect(await loadGoogleIdentity()).toBe(api);
    expect(document.head.querySelectorAll("script")).toHaveLength(0);
  });

  it("can try again after the script failed to load", async () => {
    const attempt = loadGoogleIdentity();
    document.head.querySelector("script")?.dispatchEvent(new Event("error"));
    await expect(attempt).rejects.toThrow("could not be loaded");
    expect(document.head.querySelectorAll("script")).toHaveLength(0);
    void loadGoogleIdentity().catch(() => undefined);
    expect(document.head.querySelectorAll("script")).toHaveLength(1);
  });

  it("fails when the script loads without defining the API", async () => {
    const attempt = loadGoogleIdentity();
    document.head.querySelector("script")?.dispatchEvent(new Event("load"));
    await expect(attempt).rejects.toThrow("could not be loaded");
  });
});

describe("initializeGoogleIdentity", () => {
  it("calls initialize once per page and routes credentials to the newest handler", () => {
    const api = fakeApi();
    const first = vi.fn();
    const second = vi.fn();
    initializeGoogleIdentity(api, "client-1", first);
    initializeGoogleIdentity(api, "client-1", second);
    expect(api.initialize).toHaveBeenCalledTimes(1);
    expect(api.initialize).toHaveBeenCalledWith(
      expect.objectContaining({ client_id: "client-1", ux_mode: "popup" }),
    );
    const { callback } = api.initialize.mock.calls[0][0];
    callback({ credential: "token-1" });
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledWith("token-1");
  });

  it("ignores a callback without a credential", () => {
    const api = fakeApi();
    const handler = vi.fn();
    initializeGoogleIdentity(api, "client-1", handler);
    api.initialize.mock.calls[0][0].callback({});
    expect(handler).not.toHaveBeenCalled();
  });

  it("stops delivering to a released handler, but not to a newer one", () => {
    const api = fakeApi();
    const old = vi.fn();
    const current = vi.fn();
    initializeGoogleIdentity(api, "client-1", old);
    const { callback } = api.initialize.mock.calls[0][0];
    releaseGoogleHandler(old);
    callback({ credential: "a" });
    expect(old).not.toHaveBeenCalled();
    initializeGoogleIdentity(api, "client-1", current);
    releaseGoogleHandler(old); // the old mount's cleanup must not unhook the new one
    callback({ credential: "b" });
    expect(current).toHaveBeenCalledWith("b");
  });
});
