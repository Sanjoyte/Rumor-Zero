import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { RESEND_COOLDOWN_SECONDS, useResendVerification } from "./useResendVerification";
import { MESSAGES } from "./messages";
import { ME, testSession } from "./test-helpers";

const resendMock = vi.hoisted(() => vi.fn<() => Promise<void>>());
vi.mock("@/lib/auth/auth-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/auth/auth-api")>()),
  resendVerificationEmail: resendMock,
}));

beforeEach(() => {
  vi.useFakeTimers();
  resendMock.mockReset();
  resendMock.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.useRealTimers();
});

function setup(options: Parameters<typeof useResendVerification>[0] = {}, loggedIn = false) {
  const { session, api } = testSession({}, { loggedIn });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <AuthProvider session={session}>{children}</AuthProvider>
  );
  const hook = renderHook(() => useResendVerification(options), { wrapper });
  return { ...hook, api };
}

/** One second per act(): each tick schedules the next one after React has rendered. */
function tick(seconds: number) {
  for (let i = 0; i < seconds; i += 1) act(() => vi.advanceTimersByTime(1000));
}
const send = (result: { current: { resend: () => Promise<void> } }) =>
  act(async () => {
    await result.current.resend();
  });

describe("useResendVerification", () => {
  it("is ready at once, unless the sign-up email was just sent", () => {
    expect(setup().result.current.secondsLeft).toBe(0);
    expect(setup({ cooldownOnMount: true }).result.current.secondsLeft).toBe(60);
  });

  it("counts the cooldown down once a second, to zero", () => {
    const { result } = setup({ cooldownOnMount: true });
    tick(1);
    expect(result.current.secondsLeft).toBe(59);
    tick(30);
    expect(result.current.secondsLeft).toBe(29);
    tick(29);
    expect(result.current.secondsLeft).toBe(0);
    tick(5);
    expect(result.current.secondsLeft).toBe(0);
  });

  it("measures the countdown against a deadline, so a long timer gap doesn't stretch it", () => {
    const { result } = setup({ cooldownOnMount: true });
    // One tick fires 45 s late, as in a throttled background tab: the deadline decides.
    act(() => {
      vi.setSystemTime(Date.now() + 45_000);
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.secondsLeft).toBeLessThanOrEqual(15);
    expect(result.current.secondsLeft).toBeGreaterThanOrEqual(14);
  });

  it("does nothing while the countdown runs", async () => {
    const { result } = setup({ cooldownOnMount: true });
    await send(result);
    expect(resendMock).not.toHaveBeenCalled();
  });

  it("sends, restarts the 60 s countdown and reports success", async () => {
    const onResult = vi.fn();
    const { result } = setup({ onResult });
    await send(result);
    expect(resendMock).toHaveBeenCalledTimes(1);
    expect(result.current.secondsLeft).toBe(RESEND_COOLDOWN_SECONDS);
    expect(result.current.busy).toBe(false);
    expect(result.current.status).toEqual({ tone: "success", message: MESSAGES.resendSent });
    expect(onResult).toHaveBeenCalledWith({ tone: "success", message: MESSAGES.resendSent });

    tick(60);
    await send(result);
    expect(resendMock).toHaveBeenCalledTimes(2);
  });

  it("ignores a second click while a send is running", async () => {
    let finish!: () => void;
    resendMock.mockImplementation(() => new Promise<void>((resolve) => (finish = resolve)));
    const { result } = setup();
    let first!: Promise<void>;
    act(() => {
      first = result.current.resend();
    });
    expect(result.current.busy).toBe(true);
    await act(async () => {
      await result.current.resend();
    });
    expect(resendMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      finish();
      await first;
    });
    expect(result.current.busy).toBe(false);
  });

  it("explains a 429 and restarts the countdown (the daily bucket may be the full one)", async () => {
    resendMock.mockRejectedValue(
      new ApiError({ status: 429, code: "verification_email_throttled", detail: "Wait." }),
    );
    const { result } = setup();
    await send(result);
    expect(result.current.status).toEqual({ tone: "info", message: MESSAGES.resendThrottled });
    expect(result.current.secondsLeft).toBe(RESEND_COOLDOWN_SECONDS);
  });

  it("reloads /me on 409 already_verified, so the banner goes away", async () => {
    resendMock.mockRejectedValue(
      new ApiError({ status: 409, code: "already_verified", detail: "Done." }),
    );
    const { result, api } = setup({}, true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0); // the session restores itself
    });
    expect(api.fetchMe).toHaveBeenCalledTimes(1);
    api.fetchMe.mockResolvedValue({ ...ME, is_email_verified: true });
    await send(result);
    expect(api.fetchMe).toHaveBeenCalledTimes(2);
    expect(result.current.status).toEqual({ tone: "success", message: MESSAGES.alreadyVerified });
    expect(result.current.secondsLeft).toBe(0);
  });

  it.each([
    [new ApiError({ status: 0, code: "network_error", detail: "" }), MESSAGES.network],
    [new ApiError({ status: 503, code: "backend_waking", detail: "" }), MESSAGES.waking],
    [new ApiError({ status: 500, code: "http_500", detail: "" }), MESSAGES.generic],
  ])("reports other failures as errors, without a countdown (%#)", async (error, message) => {
    resendMock.mockRejectedValue(error);
    const { result } = setup();
    await send(result);
    expect(result.current.status).toEqual({ tone: "error", message });
    expect(result.current.secondsLeft).toBe(0);
  });
});
