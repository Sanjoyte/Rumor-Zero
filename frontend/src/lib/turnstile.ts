/**
 * Loads Cloudflare Turnstile's script (explicit rendering) once. No package: the script must come
 * from Cloudflare's own URL (proxying or self-hosting it is not allowed).
 */
export const TURNSTILE_SCRIPT_URL =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export interface TurnstileRenderOptions {
  sitekey: string;
  action?: string;
  size?: "normal" | "flexible" | "compact";
  callback?: (token: string) => void;
  "expired-callback"?: () => void;
  "error-callback"?: () => void;
}

export interface TurnstileApi {
  render(container: HTMLElement, options: TurnstileRenderOptions): string;
  reset(widgetId: string): void;
  remove(widgetId: string): void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let loading: Promise<TurnstileApi> | null = null;

export function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  loading ??= new Promise<TurnstileApi>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = TURNSTILE_SCRIPT_URL;
    script.async = true;
    script.onload = () => {
      if (window.turnstile) resolve(window.turnstile);
      else fail();
    };
    script.onerror = () => fail();
    function fail() {
      script.remove();
      loading = null; // a later attempt may succeed
      reject(new Error("Turnstile could not be loaded"));
    }
    document.head.appendChild(script);
  });
  return loading;
}

/** Tests only. */
export function resetTurnstileLoaderForTests(): void {
  loading = null;
}
