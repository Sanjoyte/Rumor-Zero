/**
 * Loads Google Identity Services (GIS) once and renders Google's own sign-in button. No package:
 * the script must come from Google's URL. GIS hands back an ID token only from its own button (an
 * iframe), so the Stitch a2/a3 custom button with the inline "G" can't be used (ANALYSIS).
 *
 * `initialize` must run once per page (GIS keeps only the last call), so the credential callback
 * is a module-level handler that the mounted button replaces.
 */
export const GSI_SCRIPT_URL = "https://accounts.google.com/gsi/client";

export interface GoogleCredentialResponse {
  credential?: string;
}

export interface GoogleButtonOptions {
  type: "standard";
  theme: "outline";
  size: "large";
  text: "continue_with";
  shape: "rectangular";
  logo_alignment: "center";
  locale: string;
  width: number;
  click_listener?: () => void;
}

export interface GoogleIdentityApi {
  initialize(config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    ux_mode: "popup";
  }): void;
  renderButton(parent: HTMLElement, options: GoogleButtonOptions): void;
}

declare global {
  interface Window {
    google?: { accounts?: { id?: GoogleIdentityApi } };
  }
}

let loading: Promise<GoogleIdentityApi> | null = null;
let initializedFor: string | null = null;
let handler: ((credential: string) => void) | null = null;

export function loadGoogleIdentity(): Promise<GoogleIdentityApi> {
  const ready = window.google?.accounts?.id;
  if (ready) return Promise.resolve(ready);
  loading ??= new Promise<GoogleIdentityApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GSI_SCRIPT_URL;
    script.async = true;
    script.onload = () => {
      const api = window.google?.accounts?.id;
      if (api) resolve(api);
      else fail();
    };
    script.onerror = () => fail();
    function fail() {
      script.remove();
      loading = null; // a later attempt may succeed
      reject(new Error("Google Identity Services could not be loaded"));
    }
    document.head.appendChild(script);
  });
  return loading;
}

/** Calls `initialize` the first time (per client ID); later calls only swap the handler. */
export function initializeGoogleIdentity(
  api: GoogleIdentityApi,
  clientId: string,
  onCredential: (credential: string) => void,
): void {
  handler = onCredential;
  if (initializedFor === clientId) return;
  initializedFor = clientId;
  api.initialize({
    client_id: clientId,
    ux_mode: "popup",
    callback: (response) => {
      if (response.credential) handler?.(response.credential);
    },
  });
}

/** Stops delivering credentials to `onCredential` (the button unmounted). */
export function releaseGoogleHandler(onCredential: (credential: string) => void): void {
  if (handler === onCredential) handler = null;
}

/** Tests only. */
export function resetGoogleIdentityForTests(): void {
  loading = null;
  initializedFor = null;
  handler = null;
}
