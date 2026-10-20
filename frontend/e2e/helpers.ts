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

// The same pins as the E2E backend in playwright.config.ts.
const shellEnv = {
  ...process.env,
  REDIS_URL: "",
  EMAIL_PROVIDER: "file",
  GOOGLE_OAUTH_CLIENT_ID: "",
  PIPELINE_BACKEND: "stub",
  PIPELINE_INLINE_KICK: "False",
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
 * Files `threshold − 1` reports on a post, each by a new aged verified user, through the backend's
 * own `file_report` service, so the next report from a test account reaches the threshold. It reads
 * the threshold and the minimum account age from the platform settings (the E2E backend uses the
 * developer's own seed, so a test can't assume 5 and 24). No sign-up is used: the suite is bounded
 * by allauth's 20 sign-ups a minute. Returns how many were filed.
 */
export function seedReports(postId: string): number {
  if (!/^[0-9a-f-]{36}$/.test(postId)) throw new Error("not a post id");
  const out = runShell(
    [
      "import datetime, uuid",
      "from django.utils import timezone",
      "from apps.accounts.models import User",
      "from apps.core.services import get_platform_settings",
      "from apps.reports import services",
      "cfg = get_platform_settings()",
      "needed = max(cfg.report_threshold - 1, 0)",
      "aged = timezone.now() - datetime.timedelta(hours=cfg.report_min_account_age_hours + 1)",
      "for _ in range(needed):",
      "    tag = uuid.uuid4().hex[:10]",
      "    user = User.objects.create_user(email=f'rep-{tag}@example.test', username=f'rep_{tag}', is_email_verified=True)",
      "    User.objects.filter(pk=user.pk).update(created_at=aged)",
      "    user.refresh_from_db()",
      `    services.file_report(reporter=user, post_id='${postId}', reason='spam', details='')`,
      "print('SEEDED=' + str(needed))",
    ].join("\n"),
  );
  const seeded = /SEEDED=(\d+)/.exec(out)?.[1];
  if (seeded === undefined) throw new Error(`no count in: ${out}`);
  return Number(seeded);
}

/**
 * Changes a post's status straight in the database, the way a moderator or the pipeline will
 * (Parts 9 and 10) and the way the manual check does it in the Django shell. Runs the backend's own
 * `manage.py shell` against the same database the E2E backend uses. A fact post only for the two
 * verdicts; `removed` and `deleted` take any post.
 */
export function setPostState(
  postId: string,
  state: "verified_true" | "verified_false" | "removed" | "deleted",
) {
  if (!/^[0-9a-f-]{36}$/.test(postId)) throw new Error("not a post id");
  const fields = {
    verified_true:
      "status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=94",
    verified_false:
      "status='verified_false', verdict_source='pipeline', pipeline_verdict='false', confidence_score=90",
    removed: "status='removed'",
    // The author's soft delete (Part 12: search must not find it), whatever the status.
    deleted: "deleted_at=timezone.now()",
  }[state];
  runShell(
    `from django.utils import timezone; from apps.posts.models import Post; assert Post.objects.filter(pk='${postId}').update(${fields}) == 1`,
  );
}

/**
 * Runs the real fact-check pipeline (the stub) for one post, as the inline kick does after a post
 * commits (Part 9): `process_post` through `manage.py shell`, against the E2E backend's database.
 * Only that post: a sweep would also check the pending posts of tests running in parallel. The E2E
 * backend checks nothing by itself (`PIPELINE_INLINE_KICK=False`). Returns the post's status and
 * the confidence threshold the backend used (the developer's own PlatformSettings; seeded at 85).
 */
export function processPost(postId: string): { status: string; threshold: number } {
  if (!/^[0-9a-f-]{36}$/.test(postId)) throw new Error("not a post id");
  const out = runShell(
    [
      "from apps.core.services import get_platform_settings",
      "from apps.pipeline.processor import process_post",
      "from apps.posts.models import Post",
      `assert process_post('${postId}'), 'the post was not due for a check'`,
      `status = Post.objects.get(pk='${postId}').status`,
      "print('RESULT=' + status + ',' + str(get_platform_settings().confidence_threshold))",
    ].join("\n"),
  );
  const match = /RESULT=([a-z_]+),(\d+)/.exec(out);
  if (!match) throw new Error(`no result in: ${out}`);
  return { status: match[1], threshold: Number(match[2]) };
}

/**
 * Gives a seeded author `n` checked facts (Part 11B): each is a new `#true` fact that the real
 * pipeline (the stub, through `process_post`) labels VERIFIED, so the credibility ledger records it
 * through the real services, as the inline kick would. Returns the posts' ids.
 */
export function seedCheckedFacts(username: string, n: number): string[] {
  if (!/^[a-z0-9_]{3,30}$/.test(username)) throw new Error("not a username");
  if (!Number.isInteger(n) || n < 1 || n > 10) throw new Error("1 to 10 facts");
  const out = runShell(
    [
      "from apps.accounts.models import User",
      "from apps.pipeline.processor import process_post",
      "from apps.posts.models import Post",
      `author = User.objects.get(username='${username}')`,
      "ids = []",
      `for i in range(${n}):`,
      "    post = Post.objects.create(author=author, content=f'A checked claim {i} #true', post_type='fact', status='pending')",
      "    assert process_post(post.pk), 'the post was not due for a check'",
      "    assert Post.objects.get(pk=post.pk).status == 'verified_true', 'not verified'",
      "    ids.append(str(post.pk))",
      "print('CHECKED=' + ','.join(ids))",
    ].join("\n"),
  );
  const match = /CHECKED=([0-9a-f,-]+)/.exec(out);
  if (!match) throw new Error(`no posts in: ${out}`);
  return match[1].split(",");
}

/** An account made straight in the database, with a password: log in through the real form. */
export interface SeededAuthor {
  email: string;
  username: string;
}

/**
 * Makes a verified author with a password (and the verified `EmailAddress` row that
 * `create_superuser` also makes), so a test can log in without a sign-up: the suite is bounded by
 * allauth's 20 sign-ups a minute. Turnstile guards sign-up only, not log-in. `ageDays` makes the
 * account that many days old (emergency posts need an old enough account, Part 11C).
 */
export function seedAuthor(prefix = "author", { ageDays = 0 } = {}): SeededAuthor {
  if (!/^[a-z]{1,10}$/.test(prefix)) throw new Error("a short lower-case prefix");
  if (!Number.isInteger(ageDays) || ageDays < 0 || ageDays > 3650) throw new Error("bad age");
  const out = runShell(
    [
      "import datetime, uuid",
      "from allauth.account.models import EmailAddress",
      "from django.utils import timezone",
      "from apps.accounts.models import User",
      "tag = uuid.uuid4().hex[:10]",
      `user = User.objects.create_user(email=f'${prefix}-{tag}@example.test', username=f'${prefix}_{tag}', password='${PASSWORD}', is_email_verified=True)`,
      "EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)",
      `User.objects.filter(pk=user.pk).update(created_at=timezone.now() - datetime.timedelta(days=${ageDays}))`,
      "print('SEEDED=' + user.email + ',' + user.username)",
    ].join("\n"),
  );
  const match = /SEEDED=([^,\s]+),(\S+)/.exec(out);
  if (!match) throw new Error(`no account in: ${out}`);
  return { email: match[1], username: match[2] };
}

/** Log in through the form (Part 1) and wait until the rail shows the account. */
export async function logIn(page: Page, account: SeededAuthor) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(account.email);
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: /Log in/ }).click();
  await expect(page).toHaveURL(/\/home$/, { timeout: 30_000 });
  await expectLoggedIn(page, account.username);
}

/** A moderator's decision on a post (Part 10, 11, 11C), through the backend's own services. */
export type ModeratorAction =
  | "mark_verified"
  | "mark_false"
  | "remove_post"
  | "restore_post"
  | "keep_removed"
  | "demote_emergency";

/**
 * Has a brand-new moderator (not the one who made any earlier decision) take `action` on a post,
 * through `apps/moderation/services.py`, exactly as the admin does. `reason` is the "reason shown
 * to the author" of a removal (and the public note of a verdict). Plain letters, digits and spaces.
 */
export function moderate(postId: string, action: ModeratorAction, reason = ""): void {
  if (!/^[0-9a-f-]{36}$/.test(postId)) throw new Error("not a post id");
  if (!/^[A-Za-z0-9 ]{0,200}$/.test(reason)) throw new Error("plain text only");
  const takesNote =
    action === "remove_post" || action === "mark_verified" || action === "mark_false";
  const call = takesNote
    ? `services.${action}('${postId}', moderator=moderator, public_note='${reason}')`
    : `services.${action}('${postId}', moderator=moderator)`;
  runShell(
    [
      "import uuid",
      "from apps.accounts.models import User",
      "from apps.moderation import services",
      "tag = uuid.uuid4().hex[:10]",
      "moderator = User.objects.create_user(email=f'mod-{tag}@example.test', username=f'mod_{tag}', is_email_verified=True, role='moderator')",
      call,
      "print('MODERATED=1')",
    ].join("\n"),
  );
}

/** The emergency limits the E2E backend uses: the developer's own PlatformSettings (Part 11C). */
export interface EmergencySettings {
  minAccountAgeDays: number;
  perDay: number;
  minReputation: number;
  factPostsPerDay: number;
}

export function emergencySettings(): EmergencySettings {
  const out = runShell(
    [
      "from apps.core.services import get_platform_settings",
      "cfg = get_platform_settings()",
      "print('EMERGENCY=' + ','.join(str(v) for v in (cfg.emergency_min_account_age_days, cfg.emergency_posts_per_day, cfg.emergency_min_reputation, cfg.fact_posts_per_day)))",
    ].join("\n"),
  );
  const match = /EMERGENCY=(\d+),(\d+),(\d+),(\d+)/.exec(out);
  if (!match) throw new Error(`no settings in: ${out}`);
  const [minAccountAgeDays, perDay, minReputation, factPostsPerDay] = match.slice(1).map(Number);
  return { minAccountAgeDays, perDay, minReputation, factPostsPerDay };
}

/** The auto-label threshold the E2E backend uses: the developer's own PlatformSettings (Part 11D). */
export function confidenceThreshold(): number {
  const out = runShell(
    [
      "from apps.core.services import get_platform_settings",
      "print('THRESHOLD=' + str(get_platform_settings().confidence_threshold))",
    ].join("\n"),
  );
  const match = /THRESHOLD=(\d+)/.exec(out);
  if (!match) throw new Error(`no threshold in: ${out}`);
  return Number(match[1]);
}
