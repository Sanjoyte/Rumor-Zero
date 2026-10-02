import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  TURNSTILE_SCRIPT_URL,
  loadTurnstile,
  resetTurnstileLoaderForTests,
  type TurnstileApi,
  type TurnstileRenderOptions,
} from "@/lib/turnstile";
import { Turnstile } from "./Turnstile";

function fakeTurnstile() {
  const widgets: TurnstileRenderOptions[] = [];
  const api: TurnstileApi & { widgets: TurnstileRenderOptions[] } = {
    widgets,
    render: vi.fn((_el: HTMLElement, options: TurnstileRenderOptions) => {
      widgets.push(options);
      return `widget-${widgets.length}`;
    }),
    reset: vi.fn(),
    remove: vi.fn(),
  };
  window.turnstile = api;
  return api;
}

beforeEach(() => {
  resetTurnstileLoaderForTests();
});

afterEach(() => {
  delete window.turnstile;
  document.head.querySelectorAll("script").forEach((script) => script.remove());
});

describe("loadTurnstile", () => {
  it("injects Cloudflare's script once, from its own URL", async () => {
    const first = loadTurnstile();
    const second = loadTurnstile();
    const scripts = document.head.querySelectorAll("script");
    expect(scripts).toHaveLength(1);
    expect(scripts[0].src).toBe(TURNSTILE_SCRIPT_URL);
    expect(TURNSTILE_SCRIPT_URL).toBe(
      "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit",
    );
    const api = fakeTurnstile();
    scripts[0].dispatchEvent(new Event("load"));
    expect(await first).toBe(api);
    expect(await second).toBe(api);
  });

  it("can try again after the script failed to load", async () => {
    const attempt = loadTurnstile();
    document.head.querySelector("script")?.dispatchEvent(new Event("error"));
    await expect(attempt).rejects.toThrow("could not be loaded");
    expect(document.head.querySelectorAll("script")).toHaveLength(0);
    void loadTurnstile().catch(() => undefined);
    expect(document.head.querySelectorAll("script")).toHaveLength(1);
  });
});

describe("<Turnstile>", () => {
  it("renders the widget explicitly with the site key and passes tokens on", async () => {
    const api = fakeTurnstile();
    const onToken = vi.fn();
    render(<Turnstile siteKey="1x00000000000000000000AA" onToken={onToken} />);
    await waitFor(() => expect(api.render).toHaveBeenCalledTimes(1));
    const options = api.widgets[0];
    expect(options).toMatchObject({
      sitekey: "1x00000000000000000000AA",
      action: "signup",
      size: "flexible",
    });
    act(() => options.callback?.("token-1"));
    expect(onToken).toHaveBeenLastCalledWith("token-1");
    act(() => options["expired-callback"]?.());
    expect(onToken).toHaveBeenLastCalledWith(null);
    act(() => options["error-callback"]?.());
    expect(onToken).toHaveBeenLastCalledWith(null);
  });

  it("resets when resetKey changes and removes the widget on unmount", async () => {
    const api = fakeTurnstile();
    const onToken = vi.fn();
    const { rerender, unmount } = render(
      <Turnstile siteKey="key" onToken={onToken} resetKey={0} />,
    );
    await waitFor(() => expect(api.render).toHaveBeenCalled());
    rerender(<Turnstile siteKey="key" onToken={onToken} resetKey={1} />);
    expect(api.reset).toHaveBeenCalledWith("widget-1");
    expect(onToken).toHaveBeenLastCalledWith(null);
    unmount();
    expect(api.remove).toHaveBeenCalledWith("widget-1");
  });

  it("shows an error when the script can't load, and a field error when given one", async () => {
    const { rerender } = render(<Turnstile siteKey="key" onToken={vi.fn()} error="Bad check." />);
    expect(screen.getByRole("alert")).toHaveTextContent("Bad check.");
    document.head.querySelector("script")?.dispatchEvent(new Event("error"));
    rerender(<Turnstile siteKey="key" onToken={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("The bot check couldn't load.");
  });
});
