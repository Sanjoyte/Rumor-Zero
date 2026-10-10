import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, type Page } from "@playwright/test";
import { waitForEmailLink } from "./mailbox";

/** Shared by the auth specs: every test signs up its own account. */
export const PASSWORD = "correct-horse-battery-42";
export const BANNER = "Verify your email to post, comment and report.";

export function newAccount(prefix: string) {
  const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  return { email: `${prefix}-${id}@example.test`, username: `${prefix}_${id}` };
}

/**
 * Sign up with Cloudflare's always-pass test key. A new account lands on /verify-email (Part 2);
 * unless `stay`, the helper continues browsing read-only, which shows the unverified banner.
 */
export async function signUp(page: Page, prefix = "e2e", { stay = false } = {}) {
  const account = newAccount(prefix);
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(account.email);
  await page.getByLabel("Username").fill(account.username);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await expect(page.getByText(`Available: @${account.username}`)).toBeVisible();
  const submit = page.getByRole("button", { name: "Create account" });
  // The test widget solves itself; the button waits for its token.
  await expect(submit).toBeEnabled({ timeout: 30_000 });
  await submit.click();
  // Hashing the password (Argon2) is slow when several workers sign up at once: allow for it.
  await expect(page).toHaveURL(/\/verify-email$/, { timeout: 30_000 });
  if (!stay) {
    await page.getByRole("link", { name: /Continue browsing read-only/ }).click();
    await expect(page).toHaveURL(/\/home$/);
    await expect(page.getByText(BANNER)).toBeVisible();
  }
  return account;
}

/**
 * Sign up, then follow the verification email's link (read from the file mailbox) so the account
 * can post. Ends on /home, signed in and verified.
 */
export async function signUpVerified(page: Page, prefix = "e2e") {
  const account = await signUp(page, prefix, { stay: true });
  const link = await waitForEmailLink(account.email, "verify-email");
  await page.goto(link);
  await expect(page.getByRole("heading", { name: "Your email is verified" })).toBeVisible();
  await page.goto("/home");
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeAttached();
  return account;
}

/** A string that appears in one post only, so a test finds its own card in the shared feed. */
export function marker(prefix = "m") {
  return `${prefix}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

export async function expectLoggedIn(page: Page, username: string) {
  const rail = page.getByRole("complementary");
  await expect(rail.getByText(`@${username}`, { exact: true }).first()).toBeVisible();
  await expect(rail.getByRole("link", { name: "Log in" })).toHaveCount(0);
}

export async function logOut(page: Page) {
  await page.getByRole("button", { name: "User menu" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
}

const backendDir = path.resolve(__dirname, "../../backend");
const python =
  process.platform === "win32"
    ? path.join(backendDir, ".venv", "Scripts", "python.exe")
    : path.join(backendDir, ".venv", "bin", "python");

const shellEnv = {
  ...process.env,
  REDIS_URL: "",
  EMAIL_PROVIDER: "file",
  GOOGLE_OAUTH_CLIENT_ID: "",
};

function runShell(code: string): string {
  return execFileSync(python, ["manage.py", "shell", "-c", code], {
    cwd: backendDir,
    env: shellEnv,
    stdio: "pipe",
  }).toString();
}

/**
 * Makes a post by a brand-new verified author straight in the database, and returns its id.
 * Lets a test have a post from "a third person" (someone neither test account follows) without a
 * sign-up: the suite is bounded by allauth's 20 sign-ups a minute. A fact starts `pending`, like
 * any new fact. The text must be plain letters, digits and spaces.
 */
export function seedPost(content: string, { fact = false } = {}): string {
  if (!/^[A-Za-z0-9 ]{1,200}$/.test(content)) throw new Error("plain text only");
  const out = runShell(
    [
      "import uuid",
      "from apps.accounts.models import User",
      "from apps.posts.models import Post",
      "tag = uuid.uuid4().hex[:10]",
      "user = User.objects.create_user(email=f'seed-{tag}@example.test', username=f'seed_{tag}', is_email_verified=True)",
      `post = Post.objects.create(author=user, content='${content}', post_type='${fact ? "fact" : "opinion"}', status='${fact ? "pending" : "published"}')`,
      "print('POST_ID=' + str(post.pk))",
    ].join("\n"),
  );
  const id = /POST_ID=([0-9a-f-]{36})/.exec(out)?.[1];
  if (!id) throw new Error(`no post id in: ${out}`);
  return id;
}

/**
 * Changes a post's status straight in the database, the way a moderator or the pipeline will
 * (Parts 9 and 10) and the way the manual check does it in the Django shell. Runs the backend's own
 * `manage.py shell` against the same database the E2E backend uses. A fact post only.
 */
export function setPostState(
  postId: string,
  state: "verified_true" | "verified_false" | "removed",
) {
  if (!/^[0-9a-f-]{36}$/.test(postId)) throw new Error("not a post id");
  const fields = {
    verified_true:
      "status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=94",
    verified_false:
      "status='verified_false', verdict_source='pipeline', pipeline_verdict='false', confidence_score=90",
    removed: "status='removed'",
  }[state];
  runShell(
    `from apps.posts.models import Post; assert Post.objects.filter(pk='${postId}').update(${fields}) == 1`,
  );
}
