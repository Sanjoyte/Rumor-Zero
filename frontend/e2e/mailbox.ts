import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

/**
 * The E2E "inbox": Django runs with EMAIL_PROVIDER=file (playwright.config.ts), which writes every
 * email to backend/tmp/mail/*.log. Each message has headers, then the plain-text part first and
 * the HTML part after it.
 */
const MAIL_DIR = path.resolve(__dirname, "../../backend/tmp/mail");
const FRONTEND = "http://localhost:3000";
const SEPARATOR = /^-{79}$/m;

export type EmailRoute = "verify-email" | "reset-password";

async function messages(): Promise<string[]> {
  let names: string[];
  try {
    names = (await readdir(MAIL_DIR)).filter((name) => name.endsWith(".log"));
  } catch {
    return []; // the folder appears with the first email
  }
  const files = await Promise.all(names.map((name) => readFile(path.join(MAIL_DIR, name), "utf8")));
  return files.flatMap((content) => content.split(SEPARATOR));
}

function isTo(message: string, address: string): boolean {
  const header = /^To:[^\r\n]*/im.exec(message)?.[0] ?? "";
  return header.toLowerCase().includes(address.toLowerCase());
}

/**
 * The link of the newest email to `address` that has one for `route`: the first URL in the
 * plain-text part (it is not encoded, unlike the HTML part may be). Polls for up to 15 s.
 */
export async function waitForEmailLink(
  address: string,
  route: EmailRoute,
  timeoutMs = 15_000,
): Promise<string> {
  const link = new RegExp(`${FRONTEND}/${route}/[^\\s"'<>]+`);
  const deadline = Date.now() + timeoutMs;
  do {
    const found = (await messages())
      .filter((message) => isTo(message, address))
      .map((message) => link.exec(message)?.[0])
      .filter((url): url is string => Boolean(url));
    if (found.length > 0) return found[found.length - 1];
    await new Promise((resolve) => setTimeout(resolve, 250));
  } while (Date.now() < deadline);
  throw new Error(
    `No ${route} email for ${address} in backend/tmp/mail within ${timeoutMs / 1000} s. ` +
      "Django must run with EMAIL_PROVIDER=file: Playwright starts it that way, but a reused " +
      "`runserver` has to be started with EMAIL_PROVIDER=file too.",
  );
}
