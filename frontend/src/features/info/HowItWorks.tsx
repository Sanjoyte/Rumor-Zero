import Link from "next/link";
import type { ReactNode } from "react";
import { CategoryChip } from "@/components/ui/CategoryChip";
import { EmergencyBadge, StatusBadge } from "@/components/ui/StatusBadge";
import { CredibilitySection } from "./CredibilitySection";
import { InfoPage, P, Question, Section } from "./InfoPage";
import { INFO_NUMBERS as N } from "./numbers";

interface StatusRow {
  key: string;
  badge: ReactNode;
  means: string;
}

/** The real badges, in the order of ARCHITECTURE §4 "Badges". */
const STATUS_ROWS: readonly StatusRow[] = [
  {
    key: "opinion",
    badge: <CategoryChip type="opinion" />,
    means: "An opinion. It is published at once and is never fact-checked.",
  },
  {
    key: "pending",
    badge: <StatusBadge status="pending" />,
    means: "A fact post that is waiting for its check. It is already visible.",
  },
  {
    key: "true-pipeline",
    badge: <StatusBadge status="verified_true" verdictSource="pipeline" confidenceScore="94.00" />,
    means: "The automatic check found the claim true. The percentage is how sure it is.",
  },
  {
    key: "true-moderator",
    badge: <StatusBadge status="verified_true" verdictSource="moderator" />,
    means: "A human moderator reviewed the post and verified it.",
  },
  {
    key: "false-pipeline",
    badge: <StatusBadge status="verified_false" verdictSource="pipeline" confidenceScore="88.00" />,
    means: "The automatic check found the claim false. The percentage is how sure it is.",
  },
  {
    key: "false-moderator",
    badge: <StatusBadge status="verified_false" verdictSource="moderator" />,
    means: "A human moderator reviewed the post and marked it FALSE.",
  },
  {
    key: "review",
    badge: <StatusBadge status="under_review" />,
    means:
      "A moderator is looking at it, because the check was not sure or enough people reported it.",
  },
  {
    key: "removed",
    badge: <StatusBadge status="removed" />,
    means: "A moderator took the post down. Its place shows a notice instead of the words.",
  },
  {
    key: "emergency",
    badge: <EmergencyBadge />,
    means: `An emergency fact post, pinned for ${N.emergencyDurationHours} hours. It sits next to the post's status.`,
  },
];

const LIFECYCLE: readonly string[] = [
  "You choose Opinion or Fact when you write. Opinions publish at once.",
  "A fact post appears straight away with “Checking facts…” while the check runs.",
  `If the check is sure enough (${N.confidenceThreshold}% or more), the post becomes VERIFIED or FALSE.`,
  "If the check is unsure, or enough people report the post, a moderator reviews it.",
  "A moderator can verify it, mark it FALSE, dismiss the reports or remove the post.",
  "If your post is marked FALSE or removed, you can appeal once, and a different moderator looks again.",
];

/** `/how-it-works` (Part 15): the status table, the lifecycle, the FAQ and `#credibility`. */
export function HowItWorks() {
  return (
    <InfoPage
      title="How verification works"
      intro="Every post is text, and the author labels it Opinion or Fact. Opinions are published. Facts are checked, and the label you see tells you the result."
    >
      <Section title="What the labels mean">
        <div className="overflow-x-auto rounded-lg border border-outline-variant/30 bg-surface-container-lowest">
          <table className="w-full min-w-[32rem] text-left font-body-sm text-body-sm">
            <caption className="sr-only">Post labels and what each one means</caption>
            <thead className="border-b border-outline-variant/30 bg-surface-container-low text-on-surface">
              <tr>
                <th scope="col" className="px-space-md py-space-sm font-semibold">
                  Label
                </th>
                <th scope="col" className="px-space-md py-space-sm font-semibold">
                  What it means
                </th>
              </tr>
            </thead>
            <tbody>
              {STATUS_ROWS.map((row) => (
                <tr key={row.key} className="border-b border-outline-variant/30 last:border-b-0">
                  <th scope="row" className="px-space-md py-space-md align-top font-normal">
                    {row.badge}
                  </th>
                  <td className="px-space-md py-space-md align-top text-on-surface-variant">
                    {row.means}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="From post to label">
        <ol className="flex list-decimal flex-col gap-space-sm pl-space-lg font-body-md text-body-md text-on-surface-variant">
          {LIFECYCLE.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </Section>

      <Section title="Questions and answers">
        <Question question="Why aren’t opinions checked?">
          <P>
            An opinion is a view, not a claim that can be true or false, so there is nothing to
            check. Opinions carry an OPINION tag so nobody mistakes them for facts. A moderator can
            still remove an opinion that breaks the rules.
          </P>
        </Question>
        <Question question="How does the check work?">
          <P>
            A fact post goes into a queue and an automated check reads it. It gives a verdict and
            how sure it is. At {N.confidenceThreshold}% or more the label is set at once. Below
            that, or when the check cannot decide, the post goes to a moderator. You can add up to{" "}
            {N.sourcesPerFact} sources (a web address or a DOI) to a fact post. We store them and
            show them, but the site never opens them for you.
          </P>
        </Question>
        <Question question="What happens when a post is reported?">
          <P>
            Anyone with a verified email can report a post once. A post goes to a moderator when{" "}
            {N.reportThreshold} reports arrive within {N.reportWindowHours} hours. Only reports from
            accounts that are at least {N.reportMinAccountAgeHours} hours old, or that have already
            posted something, count towards that number. A post under review stays visible.
            Moderators can change these numbers, so the figures here are the usual ones.
          </P>
        </Question>
        <Question question="Can I appeal a FALSE label or a removal?">
          <P>
            Yes, once per post. Open the post and choose “Ask for another look”, then explain why. A
            different moderator from the one who made the first call decides, although a senior
            moderator may always decide. If the decision is overturned, the label or the post comes
            back and your credibility score returns to what it would have been.
          </P>
        </Question>
        <Question question="What is an emergency post?">
          <P>
            An emergency is a fact post about urgent safety or public-health news. It is pinned at
            the top of the feeds for {N.emergencyDurationHours} hours, and it is checked before
            other posts. It is still checked, so being pinned does not make it true. To post one:
          </P>
          <ul className="flex list-disc flex-col gap-space-xs pl-space-lg">
            <li>Your email must be verified, so we can reach you.</li>
            <li>
              Your account must be at least {N.emergencyMinAccountAgeDays} days old, to slow down
              throwaway accounts.
            </li>
            <li>
              Your credibility score must be at least {N.emergencyMinReputation}, so a record of
              false posts counts.
            </li>
            <li>
              You must not be blocked from emergencies (a block follows a FALSE emergency, below).
            </li>
            <li>
              You can post {N.emergencyPostsPerDay} emergency in any {N.emergencyDurationHours}{" "}
              hours, so the top of the feed cannot be flooded.
            </li>
            <li>
              You must still have room in your {N.factPostsPerDay} fact posts per{" "}
              {N.emergencyDurationHours} hours, because an emergency is a fact post.
            </li>
          </ul>
          <P>
            Reports weigh more on an emergency: {N.emergencyReportThreshold} reports send it to a
            moderator. If an emergency is marked FALSE, its author loses more credibility (it counts
            as three FALSE posts) and cannot post emergencies for {N.emergencyFalseCooldownDays}{" "}
            days. The block lifts early if that FALSE label is overturned on appeal.
          </P>
        </Question>
        <Question question="Why does a repost keep the original’s label?">
          <P>
            A repost has no words or label of its own. It shows the original post, so it always
            shows the original’s current label, and if that label changes, every repost shows the
            change. You cannot repost your own post, or a post labelled FALSE. If the original is
            removed or deleted, the repost says it is no longer available.
          </P>
        </Question>
      </Section>

      <CredibilitySection />

      <P>
        Ready to try it?{" "}
        <Link href="/signup" className="font-semibold text-secondary underline">
          Create an account
        </Link>
        .
      </P>
    </InfoPage>
  );
}
