import { LegalReviewNotice, P, Section } from "./InfoPage";
import { INFO_NUMBERS as N, SCORE_EVENTS } from "./numbers";

/**
 * `/how-it-works#credibility`: how the public score is worked out (ARCHITECTURE §4a). The profile's
 * widget and the owner's panel link here. It is a text description of the formula, kept in step by
 * `numbers.test.ts`.
 */
export function CredibilitySection() {
  return (
    <Section id="credibility" title="How your credibility score is calculated">
      <LegalReviewNotice>
        The wording of this section about labels and the score needs legal review before launch.
      </LegalReviewNotice>
      <P>
        Every account has a credibility score from 0 to 100. It reflects how the checks and the
        moderators have ruled on your posts, and nothing else. It is shown on your profile and in
        people lists, and never on post cards. People are never ranked by it.
      </P>
      <h3 className="font-headline-sm text-headline-sm text-on-surface">The calculation</h3>
      <P>
        You start at {N.scoreStart}. Each good event adds to a positive total and each bad event to
        a negative one. Your score is 100 × (5 + positive) ÷ ({N.scoreImaginaryEvents} + positive +
        negative), taken to the nearest whole number, with a half going up. The{" "}
        {N.scoreImaginaryEvents} imaginary events at the start keep one post from swinging the
        score. A new account moves from 50 to 55 after one TRUE and to 45 after one FALSE.
      </P>
      <h3 className="font-headline-sm text-headline-sm text-on-surface">When it is shown</h3>
      <P>
        Others see “New” until {N.scorePublicAfter} of your posts have been checked or removed. You
        always see your own real score in your settings and on your profile.
      </P>
      <h3 className="font-headline-sm text-headline-sm text-on-surface">
        What raises and lowers it
      </h3>
      <div className="overflow-x-auto rounded-lg border border-outline-variant/30 bg-surface-container-lowest">
        <table className="w-full min-w-[40rem] text-left font-body-sm text-body-sm">
          <caption className="sr-only">Every event that changes a credibility score</caption>
          <thead className="border-b border-outline-variant/30 bg-surface-container-low text-on-surface">
            <tr>
              <th scope="col" className="px-space-md py-space-sm font-semibold">
                Event
              </th>
              <th scope="col" className="px-space-md py-space-sm font-semibold">
                Whose score
              </th>
              <th scope="col" className="px-space-md py-space-sm font-semibold">
                When
              </th>
              <th scope="col" className="px-space-md py-space-sm font-semibold">
                Effect
              </th>
            </tr>
          </thead>
          <tbody>
            {SCORE_EVENTS.map((event) => (
              <tr key={event.kind} className="border-b border-outline-variant/30 last:border-b-0">
                <th
                  scope="row"
                  className="px-space-md py-space-md align-top font-label-code text-label-code font-normal text-on-surface"
                >
                  {event.kind}
                </th>
                <td className="px-space-md py-space-md align-top text-on-surface-variant">
                  {event.who}
                </td>
                <td className="px-space-md py-space-md align-top text-on-surface-variant">
                  {event.when}
                </td>
                <td className="px-space-md py-space-md align-top text-on-surface-variant">
                  {event.effect}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3 className="font-headline-sm text-headline-sm text-on-surface">What changes nothing</h3>
      <ul className="flex list-disc flex-col gap-space-xs pl-space-lg font-body-md text-body-md text-on-surface-variant">
        <li>An emergency that is verified TRUE counts as an ordinary TRUE, with no bonus.</li>
        <li>A report that a moderator dismisses costs the author and the reporter nothing.</li>
        <li>An opinion only counts if a moderator removes it.</li>
        <li>An appeal that fails costs nothing.</li>
        <li>Reposting a post that is already checked earns nothing.</li>
        <li>
          A post that goes under review changes nothing until the review ends. A late TRUE from the
          check counts only once it is public.
        </li>
      </ul>
      <h3 className="font-headline-sm text-headline-sm text-on-surface">Appeals and corrections</h3>
      <P>
        You can appeal a FALSE label and a removal once per post. If a moderator overturns the
        decision, every event it caused is cancelled for you and for everyone who reposted it, so
        scores go back to exactly what they would have been. Each event is kept in a record that
        moderators can read and that you can see for your own account in your settings, with a
        cancelled event struck through.
      </P>
    </Section>
  );
}
