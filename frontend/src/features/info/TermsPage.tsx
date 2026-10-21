import Link from "next/link";
import { InfoPage, LegalReviewNotice, P, Section } from "./InfoPage";
import { INFO_NUMBERS as N } from "./numbers";

/** `/terms` (Part 15): placeholder terms with real sections on labels and the score. */
export function TermsPage() {
  return (
    <InfoPage title="Terms" intro="The rules for using Rumor Zero.">
      <LegalReviewNotice>
        These terms are a placeholder. A lawyer must review and complete them before launch.
      </LegalReviewNotice>
      <Section title="Your account and your posts">
        <P>
          You are responsible for what you post. Posts are text only. Do not post anything illegal,
          harassing or deceptive, and do not use the site to flood or game it. You can delete your
          own posts. You keep the rights to your words, and you let us show them on the site.
        </P>
      </Section>
      <Section id="labels" title="Verification labels">
        <P>
          Fact posts get a label: VERIFIED, FALSE or UNDER REVIEW. A label is our best current
          judgement, made by an automated check or by a moderator. It can be wrong and it can
          change. It is not legal, medical or professional advice, and it does not mean we endorse
          anyone’s post. Opinions are not checked.
        </P>
        <P>
          If you disagree with a FALSE label or a removal, you can appeal it once per post.
          Moderators can remove posts that break these terms.
        </P>
      </Section>
      <Section id="score" title="Credibility score">
        <P>
          Every account has a public credibility score that is worked out from the labels and
          moderation decisions on that account’s activity, as explained on{" "}
          <Link href="/how-it-works#credibility" className="font-semibold text-secondary underline">
            How verification works
          </Link>
          . It starts at {N.scoreStart} and is shown once {N.scorePublicAfter} of your posts have
          been checked or removed. It describes the record of an account on this site, not the
          character of a person. If a decision is overturned, the score is corrected.
        </P>
      </Section>
      <Section title="Emergency posts and suspension">
        <P>
          Emergency posts have extra rules and extra consequences, described on the same page. We
          can limit or suspend an account that misuses the site.
        </P>
      </Section>
    </InfoPage>
  );
}
