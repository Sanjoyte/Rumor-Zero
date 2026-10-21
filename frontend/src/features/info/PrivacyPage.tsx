import Link from "next/link";
import { InfoPage, LegalReviewNotice, P, Section } from "./InfoPage";

/** `/privacy` (Part 15): placeholder text that says what the app really does, marked for review. */
export function PrivacyPage() {
  return (
    <InfoPage
      title="Privacy"
      intro="What Rumor Zero keeps about you, and how you can see or remove it."
    >
      <LegalReviewNotice>
        This privacy text is a placeholder. A lawyer must review and complete it before launch.
      </LegalReviewNotice>
      <Section title="What we keep">
        <ul className="flex list-disc flex-col gap-space-xs pl-space-lg font-body-md text-body-md text-on-surface-variant">
          <li>
            Your account: email address, username, display name, bio and, if you add one, a profile
            photo.
          </li>
          <li>
            Your sign-in: a password (stored only as a hash) or your Google account’s identifier.
          </li>
          <li>Your posts, comments, likes, reposts, bookmarks, follows and reports.</li>
          <li>Your credibility record: each event that changed your score, and why.</li>
          <li>
            Notifications we send you inside the site, and the emails for verifying and resetting.
          </li>
        </ul>
      </Section>
      <Section title="Who sees it">
        <P>
          Your username, display name, bio, photo, posts and credibility score are public. Your
          email address, your bookmarks and your notifications are private. Moderators can read
          reports, appeals and the record of moderation, to do their work.
        </P>
        <P>
          The site uses a few services to run: a database host, a cache, a hosting provider, error
          tracking (Sentry), Cloudflare Turnstile to block bots at sign-up, and Google if you choose
          “Continue with Google”.
        </P>
      </Section>
      <Section title="Your choices">
        <P>
          In{" "}
          <Link href="/settings" className="font-semibold text-secondary underline">
            Settings
          </Link>{" "}
          you can change your profile, download your data as a JSON file and delete your account.
        </P>
      </Section>
    </InfoPage>
  );
}
