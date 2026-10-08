import { act, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { resetGoogleIdentityForTests } from "@/lib/google-identity";
import { GoogleButton } from "./GoogleButton";
import {
  fakeGoogleIdentity,
  GOOGLE_CLIENT_ID,
  renderWithSession,
  testSession,
} from "./test-helpers";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  resetGoogleIdentityForTests();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  delete window.google;
  vi.unstubAllGlobals();
  document.head.querySelectorAll("script").forEach((script) => script.remove());
});

function answer(body: unknown, status = 200) {
  fetchMock.mockResolvedValue(Response.json(body, { status }));
}

function renderButton(props: Partial<React.ComponentProps<typeof GoogleButton>> = {}) {
  const onError = vi.fn();
  const onAttempt = vi.fn();
  const { session, api } = testSession();
  const view = renderWithSession(
    <GoogleButton
      dividerLabel="or continue with email"
      clientId={GOOGLE_CLIENT_ID}
      onError={onError}
      onAttempt={onAttempt}
      {...props}
    />,
    session,
  );
  return { onError, onAttempt, session, api, ...view };
}

describe("GoogleButton", () => {
  it("renders nothing and loads nothing without a client ID", () => {
    renderButton({ clientId: "" });
    expect(screen.queryByTestId("google-button")).toBeNull();
    expect(screen.queryByRole("separator")).toBeNull();
    expect(document.head.querySelectorAll("script")).toHaveLength(0);
  });

  it("shows Google's button with the options, and the or rule", async () => {
    const google = fakeGoogleIdentity();
    renderButton();
    await waitFor(() => expect(google.api.renderButton).toHaveBeenCalledTimes(1));
    expect(google.api.initialize).toHaveBeenCalledWith(
      expect.objectContaining({ client_id: GOOGLE_CLIENT_ID, ux_mode: "popup" }),
    );
    expect(google.buttons[0]).toMatchObject({
      type: "standard",
      theme: "outline",
      size: "large",
      text: "continue_with",
      shape: "rectangular",
      logo_alignment: "center",
      locale: "en",
      width: 400,
    });
    expect(screen.getByRole("separator", { name: "or continue with email" })).toBeInTheDocument();
  });

  it("loads Google's script when it isn't there yet", async () => {
    renderButton();
    const scripts = document.head.querySelectorAll("script");
    expect(scripts).toHaveLength(1);
    expect(scripts[0].src).toBe("https://accounts.google.com/gsi/client");
    const google = fakeGoogleIdentity();
    scripts[0].dispatchEvent(new Event("load"));
    await waitFor(() => expect(google.api.renderButton).toHaveBeenCalled());
  });

  it("draws one button under StrictMode's double effect", async () => {
    const google = fakeGoogleIdentity();
    const { session } = testSession();
    renderWithSession(
      <StrictMode>
        <GoogleButton dividerLabel="or" clientId={GOOGLE_CLIENT_ID} onError={vi.fn()} />
      </StrictMode>,
      session,
    );
    await waitFor(() => expect(google.api.renderButton).toHaveBeenCalled());
    expect(google.api.initialize).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getAllByTestId("google-iframe")).toHaveLength(1));
  });

  it("replaces its button when the client ID changes", async () => {
    const google = fakeGoogleIdentity();
    const { session } = testSession();
    const ui = (clientId: string) => (
      <GoogleButton dividerLabel="or" clientId={clientId} onError={vi.fn()} />
    );
    const { rerender } = renderWithSession(ui(GOOGLE_CLIENT_ID), session);
    await waitFor(() => expect(google.api.renderButton).toHaveBeenCalledTimes(1));
    rerender(
      <AuthProvider session={session}>{ui("other.apps.googleusercontent.com")}</AuthProvider>,
    );
    await waitFor(() => expect(google.api.renderButton).toHaveBeenCalledTimes(2));
    expect(screen.getAllByTestId("google-iframe")).toHaveLength(1);
  });

  it("sends the credential to the API and signs in with the access token", async () => {
    const google = fakeGoogleIdentity();
    answer({ status: 200, meta: { access_token: "access-from-google" } });
    const { api, onError } = renderButton();
    await waitFor(() => expect(google.api.initialize).toHaveBeenCalled());

    await act(async () => {
      google.credential("the-google-id-token");
    });

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe("/api/auth/app/v1/auth/provider/token");
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      provider: "google",
      process: "login",
      token: { client_id: GOOGLE_CLIENT_ID, id_token: "the-google-id-token" },
    });
    expect(new Headers((init as RequestInit).headers).has("authorization")).toBe(false);
    await waitFor(() => expect(api.fetchMe).toHaveBeenCalledWith("access-from-google"));
    expect(onError).not.toHaveBeenCalled();
  });

  it("shows a status while signing in, and ignores a second credential meanwhile", async () => {
    const google = fakeGoogleIdentity();
    let finish!: (response: Response) => void;
    fetchMock.mockReturnValue(new Promise<Response>((resolve) => (finish = resolve)));
    renderButton();
    await waitFor(() => expect(google.api.initialize).toHaveBeenCalled());

    await act(async () => {
      google.credential("one");
      google.credential("two");
    });
    expect(screen.getByRole("status")).toHaveTextContent("Signing in with Google…");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      finish(Response.json({ status: 200, meta: { access_token: "a" } }));
    });
  });

  it("ignores a credential while the form is busy with another sign-in", async () => {
    const google = fakeGoogleIdentity();
    renderButton({ disabled: true });
    await waitFor(() => expect(google.api.initialize).toHaveBeenCalled());
    await act(async () => {
      google.credential();
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("clears the error when Google's button is clicked", async () => {
    const google = fakeGoogleIdentity();
    const { onAttempt } = renderButton();
    await waitFor(() => expect(google.buttons).toHaveLength(1));
    google.click();
    expect(onAttempt).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["invalid_token", "Google sign-in didn't work. Try again."],
    [
      "google_email_unverified",
      "Your Google account's email address isn't verified. Verify it with Google, or sign up with email.",
    ],
    ["account_inactive", "This account can't sign in."],
    ["staff_password_login", "Staff accounts log in with their password."],
    [
      "google_link_requires_password",
      "An account with this email already exists. Log in with your password.",
    ],
  ])("reports %s", async (code, message) => {
    const google = fakeGoogleIdentity();
    answer({ status: 400, errors: [{ code, message: "server text" }] }, 400);
    const { onError, api } = renderButton();
    await waitFor(() => expect(google.api.initialize).toHaveBeenCalled());

    await act(async () => {
      google.credential();
    });

    await waitFor(() => expect(onError).toHaveBeenCalledWith(message));
    expect(api.fetchMe).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).toBeNull(); // ready to try again
  });

  it.each([
    [429, "Too many attempts. Try again in a few minutes."],
    [503, "The server is waking up. Try again in a minute."],
  ])("falls back to the usual message for a %s", async (status, message) => {
    const google = fakeGoogleIdentity();
    answer({ status }, status);
    const { onError } = renderButton();
    await waitFor(() => expect(google.api.initialize).toHaveBeenCalled());
    await act(async () => {
      google.credential();
    });
    await waitFor(() => expect(onError).toHaveBeenCalledWith(message));
  });

  it("can try again after a failure", async () => {
    const google = fakeGoogleIdentity();
    answer({ status: 400, errors: [{ code: "invalid_token", message: "x" }] }, 400);
    const { onError, api } = renderButton();
    await waitFor(() => expect(google.api.initialize).toHaveBeenCalled());
    await act(async () => {
      google.credential("first");
    });
    await waitFor(() => expect(onError).toHaveBeenCalledTimes(1));

    answer({ status: 200, meta: { access_token: "second-access" } });
    await act(async () => {
      google.credential("second");
    });
    await waitFor(() => expect(api.fetchMe).toHaveBeenCalledWith("second-access"));
  });

  it("explains it when Google's script can't load, and keeps the or rule", async () => {
    renderButton();
    document.head.querySelector("script")?.dispatchEvent(new Event("error"));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Google sign-in couldn't load. Check your connection, or use email.",
    );
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });

  it("stops listening when it unmounts", async () => {
    const google = fakeGoogleIdentity();
    const { unmount } = renderButton();
    await waitFor(() => expect(google.api.initialize).toHaveBeenCalled());
    unmount();
    await act(async () => {
      google.credential();
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("renders into a fresh container after a remount, without calling initialize again", async () => {
    const google = fakeGoogleIdentity();
    const first = renderButton();
    await waitFor(() => expect(google.api.renderButton).toHaveBeenCalledTimes(1));
    first.unmount();
    renderButton();
    await waitFor(() => expect(google.api.renderButton).toHaveBeenCalledTimes(2));
    expect(google.api.initialize).toHaveBeenCalledTimes(1);
    answer({ status: 200, meta: { access_token: "a" } });
    await act(async () => {
      google.credential();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
