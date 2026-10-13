# Plan: Part 11, Appeals & removed-post tombstones

- **Status:** APPROVED by the user (Sanjoy Rozario) on 2026-10-13, together with the six decisions and the defaults
  below; drafted 2026-10-13 by Claude (Opus 5.5). **IMPLEMENTED 2026-10-13** by Claude (Sonnet 5.5); what changed on the way
  (the appeal row lock and the explicit Escalate exemption were dead code and are gone; the modal's single flight is a ref;
  the E2E helpers are `seedAuthor`, `logIn` and `moderate`) is in `task.md` Part 11 and HANDOFF.
- **Implement with:** Sonnet 5.5 · high (task.md).
- **Evidence (read-only):** HANDOFF, MEMORY, `task.md` Parts 10/11/11B/11C/13, ARCHITECTURE §2/§3/§4/§4a/§8/§9/§10,
  ANALYSIS (c-7, f-2, b-2 rows, the appeal row), STRUCTURE; code: `apps/moderation/{models,rules,services,admin,
  forms,roles}.py` and migration 0002, `apps/posts/{models,serializers,services,views}.py`, `apps/pipeline/
  {routing,processor}.py`, `apps/reports/{services,views,exceptions}.py`, `apps/social/{views,feed,engagement}.py`,
  the moderation tests; one Explore pass over the frontend (types, `PostDetail`, `VerdictBlock`, `PostCard`,
  `FeedList`, `ProfilePosts`, `StatusBadge`, the report modal and button, Stitch b3/c1, `e2e/helpers.ts`).
- **Design review:** a Plan-agent review of this draft against the code and Django 5.2's admin source, run **before**
  approval. Its findings are folded in below and marked "(review)".

## Context

Part 11 builds the "Request another look" path of guide §8.4 / §16 (c-7, ANALYSIS f-2) and proper tombstones:
- the author of a **FALSE-labelled** post can appeal the label (the post goes back to the review queue);
- the author of a **removed** post can appeal the removal (the post stays hidden and is listed in the queue);
- moderators resolve label appeals with Part 10's Mark verified / Mark FALSE, and removal appeals with two new
  actions, **Restore post** and **Keep removed**; the moderator who made the original call can't resolve the appeal
  unless they are a senior;
- the author sees `can_appeal`, the APPEAL PENDING chip and the outcome; removed posts get a `RemovedPostCard`
  (public and author variants) on the post page and on the author's own profile.

**Dependency check (2026-10-13).** Part 11 depends only on **Part 10** (`[x] Done (2026-10-13)`, committed as
`582905b`). Its chain is Done: 9, 8, 5, 4, 1, 0C, 0A/0B/0D, plus 2, 3, 6, 7, 7B. Open but not blocking: Part 3
criterion 4 (the real-Google check) and CI for Parts 2 to 10 (not reported yet).

**Workspace:** HEAD `582905b` ("Implemented Part 10…"), tree clean. HANDOFF still says Part 10 is uncommitted; step 0
fixes that line.

**Already in place:**
- `posts.pre_removal_status` (Part 4), `FlaggedReason.APPEAL` and `merge_flag`'s appeal rules (Part 8: `appeal`
  stays `appeal`; an appeal onto a post under review for anything else raises), the `appeal` throttle rate
  (`5/day`, `settings.py:198`), `ActionKind.RESTORED` (Part 10), `NotAuthorError` (403 `not_author`).
- Remove already stores `pre_removal_status` and keeps the reason on `ModerationAction.public_note`; it never
  touches `Post.verdict_note`.
- Frontend: `Post.can_appeal` / `appeal_status` / `AppealStatus` in `types.ts`, `AppealPendingBadge` (amber
  `verdict-review` tone, `gavel`) in `StatusBadge.tsx`, rendered on cards (`post-card-props.ts:19`) and on the post
  page (`PostDetail.tsx:191`). The backend always sends `can_appeal: false, appeal_status: null` today.

## Your decisions (2026-10-13)

1. **Restore of a fact the pipeline had already checked goes to the review queue.** When `pre_removal_status` is
   `pending` and the pipeline has had its say (`pipeline_checked_at` set, or `pipeline_attempts ≥ MAX_ATTEMPTS`),
   Restore puts the post **under review for the pipeline** (`pre_review_status=pending`, the clock starts now) and a
   moderator gives the label. A fact the pipeline never finished goes back to `pending` and is checked as usual.
   Every other `pre_removal_status` is restored as is. A finished check is never run again.
2. **Keep removed writes a new audit kind, `kept_removed`** ("Kept removed"). One migration widens
   `moderation_action_valid` (Part 10 meant the list to be final; this kind was missing).
3. **The removal reason reaches the author in a new key, `removal_reason`** (24 keys): the `public_note` of the post's
   latest `removed` row for the author of a removed post, `""` for everyone else and every other post.
   `verdict_note` keeps meaning only the label's note.
4. **Your own profile lists your removed posts** (the author tombstone with your text, the reason and the appeal
   state or button). Visitors, feeds, bookmarks and the profile counters are unchanged.
5. **Remove during an open label appeal is allowed and closes the appeal as `upheld`**, linked to the `removed` row;
   the different-moderator rule applies to it.
6. **Restore post and Keep removed take internal notes only.** The author sees the outcome in plain words and the
   original removal reason.

## Scope

**In:** the `Appeal` model, the `appeal` FK and the `kept_removed` kind; `file_appeal`; Restore and Keep removed;
the different-moderator rule; the appeal endpoint; `can_appeal` / `appeal_status` / `removal_reason`; the author's
removed posts on their profile; the admin queue, filter, inline, `AppealAdmin`, the two actions and Escalate on
removal appeals; the `view_appeal` permission; the frontend (`AppealModal`, `AppealButton`, `RemovedPostCard`, the
outcome); tests, E2E, docs, `docs/test-command.md`.

**Not in Part 11:** reputation events and their reversal (11B), the emergency branches (11C), `appeal_resolved` and
other notifications (13), the appeal link on negative ledger rows (11B/14), export of appeals (14). No new
dependency, service or env variable.

## Design

### Data model (migrations `moderation.0003_appeal`, `moderation.0004_appeal_permission`)

**`moderation.Appeal`** (table `moderation_appeal`), per ARCHITECTURE §2:

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | |
| post | `OneToOneField(Post, CASCADE, related_name="appeal")` | §2's "FK CASCADE, unique" in Django's idiom (a unique FK is warning W342); one appeal per post for life |
| author | FK users CASCADE, `related_name="appeals"` | the post's author (the service checks it); its index serves account deletion and export |
| kind | `label` \| `removal` | `appeals_kind_valid` |
| reason | varchar(500), blank | trimmed; code points |
| status | `open` \| `upheld` \| `overturned`, default open | `appeals_status_valid` |
| original_moderator | FK users SET_NULL null, `related_name="+"` | who made the call being appealed (below) |
| resolved_by | FK users SET_NULL null, `related_name="+"` | |
| resolved_at | timestamptz null | `appeals_resolution_consistent`: `open` exactly while `resolved_at` is null |
| created_at | timestamptz, `default=timezone.now` | the service passes `now` |

`__str__` leaves the reason out (as reports do). Written only by `apps/moderation/services.py`. Not append-only (its
status changes once); rows go only with the post or the account (CASCADE).

**`ModerationAction`:** `appeal = FK(Appeal, SET_NULL, null, related_name="moderation_actions")`, set on the row of
the action that **resolves** an appeal (Mark verified/FALSE or Remove on a label appeal, Restore, Keep removed).
`ActionKind.KEPT_REMOVED = "kept_removed", "Kept removed"`; the migration alters the field's choices and replaces
`moderation_action_valid` (11 kinds).

**`0004_appeal_permission`:** a data migration in the 0002 pattern with its **own frozen lists** (0002's plus
`moderation.view_appeal` for Moderators), `create_permissions` for the stub apps, depending on `0003` and the latest
migration of every app it names. `roles.MODERATOR_PERMISSIONS` gains `moderation.view_appeal`.
- (review) **Its reverse re-sets 0002's frozen lists**, not 0002's `revoke` (which clears both groups and would leave
  moderators with nothing after `migrate moderation 0003`).
- (review) **0003 can't be reversed once a `kept_removed` row exists** (the old 10-kind check would refuse it).
  Recorded in ARCHITECTURE §2; the rollback check runs on a database with appeals but no `kept_removed` row.
- (review) `test_roles.py` keeps its 0002 tests against 0002's own lists and adds 0004 tests: its lists equal
  `roles.py`, grant is idempotent, revoke returns to 0002's lists; `moderation.change_appeal` /
  `moderation.delete_appeal` join the "lacks" cases. Seniors need nothing extra (the groups are cumulative).

### Who made the original call (`original_moderator`, set by `file_appeal`)

- **Label appeal:** the moderator of the post's latest `marked_false` row **when `verdict_source=moderator`**; null for
  a pipeline FALSE. (Not `post.moderated_by`: a later Dismiss of reports on the FALSE post would make the dismisser
  look like the one who labelled it.)
- **Removal appeal:** the moderator of the post's latest `removed` row.
- Null (no row, or the account was deleted) means any moderator may resolve it. If two moderators marked a post FALSE
  over time, only the latest counts (recorded in §4).

### Rules (`apps/moderation/rules.py`, still pure)

- New acts `Act.RESTORE`, `Act.KEEP_REMOVED` (`REMOVAL_APPEAL_ACTS`). `APPEAL_REQUIRE_DIFFERENT_MODERATOR = True`
  (the §4 name, a code constant).
- `refusal(act, post, moderator, *, appeal)`: `appeal` is the post's **open** appeal or None, a **required keyword**
  (review: with a default, a call site that forgets it would silently hide Restore and skip the original-moderator
  rule; the existing calls in `admin.py` `render_change_form` and `_moderate` are updated). Whether an act resolves
  an appeal is derived from the `appeal` passed, never from `flagged_reason == appeal` alone (a flagged post with no
  row, from a factory or E2E state, must not crash). `open_appeal(post)` lives in `admin.py`/`services.py`, not in
  the pure module (reading `post.appeal` can query). Order: `deleted`, `own_post`, `opinion` (verdicts), then the
  state check, then the appeal check:
  - Verdicts, Dismiss: as Part 10 (a post under appeal has the flag `appeal`, so Dismiss answers `no_reports`).
  - Remove: as Part 10 (any status but removed; under review needs a returnable `pre_review_status`).
  - **Escalate:** a post under review, **or a removed post with an open removal appeal**; not twice.
  - **Restore / Keep removed:** `removed` with an open **removal** appeal, else new `no_removal_appeal` ("no open
    removal appeal"). Restore also needs a `pre_removal_status` the type can return to (opinion: `published`; fact:
    `pending`, `verified_true`, `verified_false`), else `no_prior_status`.
  - **New `original_moderator`** ("you made the first decision"): the act would resolve an open appeal (a verdict or
    Remove on a post flagged `appeal`, or Restore / Keep removed) and `appeal.original_moderator_id` is the moderator,
    who is neither a senior (`role=senior_moderator`) nor a superuser. Escalate is never refused for it (escalating is
    what the original moderator should do).
- `transition(act, post, *, moderator, now, appeal, public_note="")` returns `Effect` with a new
  `appeal_status` (`overturned` / `upheld` / None):
  - Mark verified with an open label appeal → `overturned`; Mark FALSE → `upheld`; Remove → `upheld` (decision 5).
  - **Restore:** target = `pre_removal_status`; if it is `pending` and **`routing.pipeline_had_its_say(post)`** (new,
    pure, beside `is_awaiting_check`, review: routing rules live there: `pipeline_checked_at` set or
    `pipeline_attempts ≥ MAX_ATTEMPTS`): `status=pending`, then `routing.enter_review(post, PIPELINE, now)`
    (decision 1); otherwise `status=target`, `flagged_reason=None`. Both clear `pre_removal_status` and
    `escalated_at`. Kind `restored`; appeal `overturned`. `verdict_source`, `verdict_note`, `confidence_score` and every
    `pipeline_*` field stay (a restored label keeps its source and %). A post removed mid-claim is safe: its answer was
    dropped as `IGNORED` and the stale lease only delays the next try (review).
  - **Keep removed:** status stays `removed`; `flagged_reason=None`, `escalated_at=None`. Kind `kept_removed`;
    appeal `upheld`.
  - Escalate on a removed post sets `escalated_at` only.
- The §4 rows are re-tabled in `test_rules.py` "a second way", as Part 10 did. (review) Its invariant
  `flagged_reason is None or status == under_review` (`test_rules.py:356`) becomes "… or (`removed` and flag
  `appeal`)"; the matrix gains `pre_removal_status` and the pipeline's say **for removed posts only**, so it doesn't
  grow twentyfold.

### Services (`apps/moderation/services.py`)

- **`_perform`:** after the post's row lock, lock its open appeal (`Appeal.objects.select_for_update().filter(post=…,
  status=open).first()`; **lock order post → appeal**, the same as `file_appeal`), pass it to `refusal` and
  `transition`, and when `effect.appeal_status` is set, write `status`, `resolved_by`, `resolved_at` in one save and
  link the audit row (`appeal=`). `_SAVED_FIELDS` is unchanged (it already covers every field Restore writes).
- **`restore_post(post_id, *, moderator, notes="", now=None)`** and **`keep_removed(…)`**: thin wrappers like the
  other five (no `public_note`, decision 6). A fact restored to `pending` gets the same after-commit inline kick as
  a new fact (review: otherwise it waits for the sweeper): `posts.services` exposes the existing `_kick_pipeline`
  on-commit step as one public helper that `create_post` also uses (it still never raises; off in tests unless a test
  turns it on).
- **`file_appeal(*, author, post_id, reason="", now=None)`** → `Appeal`. Raises `PostNotFound`, `NotPostAuthor`,
  `AlreadyAppealed`, `NotAppealable` (domain errors; the view maps them). In one `atomic()`:
  1. lock the post: `not_deleted()`, `FOR NO KEY UPDATE`, `of=("self",)`, `defer("pipeline_result")` (the lock
     reports, reposts, the pipeline and moderators use); `now` is taken after the lock;
  2. none → `PostNotFound`; another author → `NotPostAuthor`; any earlier appeal (open or resolved) →
     `AlreadyAppealed`; status not `verified_false` / `removed` → `NotAppealable` (a FALSE post under review for
     reports has status `under_review`: not appealable until that review ends, as HANDOFF's Part 8 note asks);
  3. label: `routing.enter_review(post, APPEAL, now)` (→ `under_review`, `pre_review_status=verified_false`, the clock
     starts); removal: `flagged_reason=appeal` only (status stays `removed`, `review_started_at` stays null, so the
     Part 10 check holds); save those fields + `updated_at`;
  4. create the `Appeal` (kind, trimmed reason, `original_moderator` as above, `created_at=now`).
  The duplicate check is race-free behind the lock (no `IntegrityError` catch, as in Part 8). A removed post can't be
  reported (404), and a label appeal is never seen by the pipeline (`verdict_source` is set), so nothing else races it.

**What the pipeline and reports see:** unchanged code. A restored `pending` post is back in `awaiting_check_q`; a
post restored into review isn't (`flagged_reason=pipeline`); a post under a label appeal keeps `appeal` when reports
cross the threshold (`merge_flag`), and Mark verified/FALSE action those reports.

### API: `POST /api/v1/posts/{id}/appeal/` (`apps/moderation/{views,urls,serializers,exceptions}.py`)

- `AppealView` (POST only; `never_cache`): `IsAuthenticated` + `IsEmailVerified`, `ScopedRateThrottle` scope
  `appeal` (5/day) **for POST only** (`get_throttles()` by method, as `PostListView`; review: DRF throttles before it
  resolves the handler, so a GET would otherwise use up the 5 and then answer 405). Order as the report view: 401,
  403 `email_unverified` (neither counts), 429, malformed id → 404,
  body → 400, then the service: 404 (unknown or deleted), **403 `not_author`** (`NotAuthorError` reused), **409
  `already_appealed`** "You already asked for another look at this post.", **409 `not_appealable`** "Only posts
  labelled FALSE or removed can be appealed.". From the throttle on, every answer counts.
- Body `{reason?}`: optional, trimmed, ≤ 500 code points ("Keep it to 500 characters."); undeclared fields ignored.
- **201 with the post object**, re-read with `Post.objects.not_deleted().for_list(request.user)` (review: not
  `visible()`, which drops the removed post of a removal appeal), so the page shows UNDER REVIEW and the chip at
  once. Included from `rumor_zero/urls.py` like `apps.reports.urls`.

### The post object (`PostSerializer`, `PostQuerySet.for_list`)

- New helper `apps/moderation/queries.py` `with_appeal_fields(queryset, viewer)`, called from `for_list` (a
  function-local import, as `with_engagement` is). For a signed-in viewer it annotates, inside the same query:
  - `appeal_status` = `Case(When(author=viewer, then=Subquery(the appeal's status)))`, else null;
  - `removal_reason` = `Case(When(author=viewer, status=removed, then=Coalesce(Subquery(public_note of the latest
    `removed` row, by `modaction_post_created_idx`), "")))`, else `""`.
  A visitor gets `Value(None)` / `Value("")`. `appeal_defaults(post)` sets both on a new post's 201 (next to
  `engagement_defaults`). **List query counts don't change.**
- `PostSerializer` (strict reads, like the counts): `appeal_status` for the author only; `can_appeal = is_mine and
  appeal_status is None and status in (verified_false, removed)`; `removal_reason` for the author of a removed post,
  else `""`. **24 keys.** The tombstone rule is unchanged (`removal_reason` is `""` there anyway).
- (review) Every runtime path already goes through `for_list` or the defaults (Recent, the 201, the detail,
  Following, bookmarks, the profile, `social/serializers.py` hydration). Two tests serialize a bare post and change
  on purpose: `apps/reports/tests/test_reported_by_me.py:102` (add `appeal_defaults`) and
  `apps/social/tests/test_engagement_counts.py:120-132` (the "forgot `for_list`" test lists the two new attributes).

### The author's removed posts on their own profile (`apps/social/views.py`, `feed.py`)

- `UserPostsView`: when the viewer is the profile's owner, the post side is `not_deleted()` instead of `visible()`
  (the `?post_type=` filter still applies). `feed.load_entries(…, own_removed=True)` hydrates with
  `not_deleted().exclude(Q(status=removed) & ~Q(author=viewer))`, so your own removed posts load while a repost of
  someone else's removed post stays the "no longer available" stub. Everyone else's view, the feeds, bookmarks and
  the counters are unchanged. The query counts stay the same.

### Admin (`apps/moderation/admin.py`)

- **Queue (`QueueFilter` default):** `status=under_review` **or** (`status=removed` and `flagged_reason=appeal`), not
  deleted.
- **New filter "appeal"** (`AppealFilter`): FALSE label / Removal → posts with an **open** appeal of that kind.
- **Columns:** Reason shows "Appeal (FALSE label)" / "Appeal (removal)" (from the flag and the status: `appeal` +
  `under_review` is a label appeal, `appeal` + `removed` a removal appeal); Waiting and the default order use one
  expression, "in the queue since" = `review_started_at` for a post under review, the appeal's `created_at` for a
  removed post with an open appeal (`Case`, asc, nulls last; an expression in `ordering` skips admin check E033, and
  `o=` sorting and the `-pk` tiebreak still work, checked by the review in Django's source).
  `list_select_related = ("author", "appeal")`: the page stays a constant number of queries. The order still leads
  with `-report_count` (Part 10), so a much-reported removed post's appeal sorts high; kept as is.
- **Actions:** `restore_posts` ("Restore posts", "Restored N posts.") and `keep_removed` ("Keep removed", "Kept N
  posts removed."), same confirmation page (internal notes only; the "after" column shows "Under review" when
  decision 1 applies), same skip messages ("1 you made the first decision", "1 no open removal appeal"). Post-page
  buttons "Restore post" / "Keep removed" come from the same `refusal` loop; Escalate is offered on removal appeals.
  `_moderate` selects the appeal with the posts and passes `open_appeal(post)` to the rules.
- **`AppealInline`** on the post page (read-only, first of the three inlines): kind, status, reason, created,
  original moderator, resolved by, resolved at. View with `moderation.view_appeal`. (review) Its `get_queryset`
  `select_related("original_moderator", "resolved_by")`, or a post page with an appeal costs more queries than one
  without; Part 10's equal-count test (`test_admin_queue.py:312`) gets a resolved appeal on the busy post.
- **`AppealAdmin`** (every model is registered): read-only list for moderators: created, post (linked excerpt),
  author, kind, status, original moderator, resolved by/at; filters kind, status, created; search author username;
  `list_select_related = ("post", "author", "original_moderator", "resolved_by")` with `post__pipeline_result`
  deferred; `HistoryNeedsLog`; no add/change/delete. The reason shows on an appeal's own page, not the list.
- `ModerationActionAdmin` shows the `appeal` link.

### Frontend

- **Types and helpers:** `Post.removal_reason: string`; `makePost` gets `removal_reason: ""`.
- **`src/features/appeals/`** (new):
  - `appeals-api.ts`: `APPEAL_PATHS`, `appealPost(postId, {reason}) → Post` (the `reports-api` pattern).
  - `messages.ts`: `APPEAL_MESSAGES`, `appealFailure(error)` → `already` / `not_appealable` / `gone` / `fields` /
    `other` (verify, 429 with `waitText`, 401, network, waking, failed).
  - `AppealModal` (ReportModal's pattern: `Modal` `title="Request another look"`, `eyebrow="Appeal"`, `icon="gavel"`,
    `footerTone="plain"`; the post quoted; one line saying what is appealed — "Your post is labelled FALSE." or "A
    moderator removed your post." plus "Reason given: …"; `Textarea` "Why should we look again?" optional,
    `maxCount` 500; an info `Alert` "What happens next": a moderator who didn't make the first decision looks again,
    a FALSE post shows UNDER REVIEW meanwhile, one request per post; Cancel / **Send request**; the fieldset lock
    and the focus-after-error effect). Outcomes: 201 → close, toast "Request sent. A moderator will take another
    look.", the caller gets the new post; 409 `already_appealed` / `not_appealable` → close, toast, the caller
    reloads; 404 → close, "This post is no longer available."; 403 `email_unverified` → warning; 400 → the field;
    429 → "You've asked for another look too often today. Try again in about N hours."; others → error `Alert`, text
    kept.
  - `AppealButton` ("Request another look", b3's label minus "/ APPEAL VERDICT"): rendered only for
    `is_mine && can_appeal`; an unverified email → `aria-disabled` with a `useId` hint and a toast; the modal is
    built on the first click and kept; one `<button>` throughout.
  - `AppealOutcome`: the author's line, from `appeal_status` and the status — open: "You asked for another look. A
    moderator who didn't make the first decision will review it."; upheld + removed: "…A moderator reviewed it, and
    the post stays removed." (fits Keep removed and decision 5); upheld + `verified_false`: "…and the FALSE label
    stays."; upheld otherwise: "…and the decision stands."; overturned: "…A moderator reversed the decision." (the
    badge shows the result; the API doesn't send the kind, and these words fit both kinds).
- **`RemovedPostCard`** (`src/features/posts/`, c1's tombstone classes, our `block` glyph): public variant = today's
  tombstone ("Removed by a moderator" on a card); author variant (`is_mine`) adds "Only you can see this text.", the
  claim (the card's fonts), "Reason given: …" (when `removal_reason` isn't blank) and the appeal area (`AppealButton`
  / chip + `AppealOutcome`). (review) A successful appeal is kept as `filed: Post | null` and the card shows
  `filed?.id === post.id ? filed : post`, so the chip survives `FeedCard` building a new object on every poll.
  - `FeedList`'s `FeedCard` renders it for a removed post (loaded or polled); repost stubs are unchanged.
  - (review) `PostCard` keeps a removed guard that delegates to `RemovedPostCard`'s public variant, so no caller can
    ever render a removed post's text or action bar (the `/dev/ui` gallery in `features/dev/StitchSections.tsx`
    renders one; it gains the author variant too). The six `PostCard.test.tsx` cases that pin the branch change on
    purpose.
  - `/p/[id]` (page layout): a removed post renders it with the back link and `AuthorRow`. (review) The public
    variant keeps the page's wording "This post was removed by a moderator."; the author variant keeps the claim as
    the page's `<h1>` and "Only you can see this text.", adds the reason and the appeal area, and keeps `SourceList`
    and Delete; no action bar, verdict block or comments (as today). It replaces the author's warning `Alert`.
    Metadata is unchanged. `e2e/post-detail.spec.ts`'s removed-post test (lines 186-206) keeps passing as written;
    it is listed as changed only if a selector moves.
- **FALSE post on `/p/[id]`:** `VerdictBlock` gets the `AppealButton` at the bottom (b3's place, `ml-auto`) for the
  author. (review) **`AppealOutcome` is rendered by `PostDetail` beside `VerdictBlock`, not inside it**:
  `VerdictBlock` returns early for a published opinion ("Opinions aren't fact-checked.", lines 69-75), so a restored
  opinion's outcome would never show. A successful appeal `patch()`es the page with the returned post.
- Cards never get the button (b3 only); they already show the chip.

## Defaults where the docs are silent (approved with the plan)

- The 201 answer is the post object; 409 `not_appealable` for a status that can't be appealed; 409
  `already_appealed` wins over it (a second try after an outcome says "already").
- `can_appeal` depends only on the post (the button handles an unverified email, as Report does).
- **Superusers are exempt** from the different-moderator rule, as from the own-post rule; Escalate is exempt.
- A deleted post can't be appealed (404, its author included) and its open appeal simply stays open (moderators refuse
  deleted posts; the queue hides them).
- `pre_removal_status` is cleared by Restore; Restore and Keep removed clear `escalated_at`.
- Appeals are linked on the resolving action's audit row only (not on Escalate).
- Moderators see appeals (`view_appeal`); seniors get nothing extra.
- A fact restored to `pending` is kicked after the commit like a new fact; a restored post reappears in Recent at
  once and in a follower's cached Following page within `FEED_CACHE_SECONDS`.
- **Recorded deviation:** `task.md` Part 10's note says Restore never touches `review_started_at`; with decision 1 a
  Restore into the review queue starts the clock (through `enter_review`), which the database check requires.
  Restore to any other status leaves it null, as the note says.
- E2E logs in a **seeded** author (no sign-up: the suite is at 16 of allauth's 20 a minute). (review) Feasible:
  Turnstile guards sign-up only, and the seeded user mirrors `create_superuser`'s verified `EmailAddress` row.

## Files

**New (backend):** `apps/moderation/{views,urls,serializers,exceptions,queries}.py`,
`migrations/0003_appeal.py`, `migrations/0004_appeal_permission.py`, tests `test_appeal_models.py`,
`test_services_appeals.py`, `test_api_appeal.py`, `test_appeal_fields.py`.
**Changed (backend):** `apps/moderation/{models,rules,services,admin,roles}.py` (+ `forms.py` help text if needed),
`apps/posts/{models,serializers,views,services}.py` (`for_list`, the 24 keys, `appeal_defaults` on create, the public
kick helper), `apps/pipeline/routing.py` (`pipeline_had_its_say`), `apps/social/{views,feed}.py`,
`rumor_zero/urls.py`; tests `test_rules`, `test_services`, `test_races`, `test_pipeline_interplay`,
`test_admin_queue`, `test_admin_actions`, `test_permissions`, `test_roles`, `test_models`, `pipeline/tests/
test_routing.py`, the posts key-list tests (`test_api_create`, `test_api_detail`), `reports/tests/
test_reported_by_me.py`, `social/tests/test_engagement_counts.py`, the profile list tests.
**New (frontend):** `src/features/appeals/{appeals-api,messages,AppealModal,AppealButton,AppealOutcome}` + tests,
`src/features/posts/RemovedPostCard.tsx` + test, `e2e/appeals.spec.ts`.
**Changed (frontend):** `lib/api/types.ts`, `features/posts/{PostDetail,VerdictBlock,PostCard,FeedList,
post-card-props,test-helpers}` and their tests, `features/social/ProfilePosts.test.tsx`,
`features/dev/StitchSections.tsx` (both tombstone variants), `e2e/helpers.ts` (`seedAuthor` with a password +
`logIn`, `removeWithService`, `resolveAppeal`), `e2e/post-detail.spec.ts` only if a selector moves.
**Docs:** ARCHITECTURE §2/§3/§4/§8/§9/§10, ANALYSIS (a c-43 entry; b-2 Removed and the appeal row marked built),
STRUCTURE, MEMORY (durable findings only), `task.md` (criteria, decisions, deviations, both status spots, notes for
11B/13/14), `docs/test-command.md` (a `### Part 11` section in both guides), HANDOFF.

## Steps (each ends green before the next)

0. Save this plan under `docs/agents/plans/`, fix HANDOFF's "Part 10 uncommitted" line, `docker compose ps` (start the
   containers if they are down), measure the baselines (`pytest`, `npm test`).
1. Models + `0003_appeal` (+ `ruff check --fix . ; ruff format .`), `roles.py` + `0004_appeal_permission`;
   `test_appeal_models`, `test_roles`, `test_models`; `makemigrations --check`.
2. Rules (acts, refusals, transitions, the original-moderator rule) + `test_rules`.
3. Services (`_perform` with the appeal, `restore_post`, `keep_removed`, `file_appeal`) + service, race and pipeline
   interplay tests.
4. API (view, serializer, exceptions, urls) + `test_api_appeal`.
5. Post object (`with_appeal_fields`, 24 keys, defaults) + per-viewer tests and the existing key/query-count tests.
6. Profile list for the owner + tests.
7. Admin (queue, filter, columns/order, actions, buttons, inline, `AppealAdmin`) + admin tests (query counts).
8. Frontend: types/helpers → `appeals/` → `RemovedPostCard` → `FeedList`/`PostCard` → `PostDetail`/`VerdictBlock` →
   tests; lint, typecheck, `lint:tokens`, `format:check`.
9. E2E helpers + `e2e/appeals.spec.ts`; the full suite.
10. Docs; `docs/test-command.md` Part 11 (Linux blocks extracted and run verbatim, output diffed); browser check;
    mutation checks; `task.md`, MEMORY, HANDOFF.

## Tests

**Backend**
- Models: each check (kind, status, resolution consistency), one appeal per post, CASCADE with the post and the
  author, the audit row's `appeal` SET_NULL, `kept_removed` accepted, `__str__` without the reason.
- Rules (pure, every act × every starting state the checks allow, with and without an open appeal of each kind):
  refusals in order, the original-moderator matrix (moderator / senior / superuser / null original; each resolving act;
  Escalate exempt), Restore targets (each `pre_removal_status` × "pipeline had its say" by `pipeline_checked_at` and
  by attempts), Keep removed, Remove closing a label appeal, only the allowed fields change.
- Services: `file_appeal` for each status (only `verified_false` and `removed`), another author, deleted, unknown,
  twice (open, upheld, overturned), `original_moderator` (pipeline FALSE → null; moderator FALSE after a Dismiss →
  the labeller; removal → the remover), the fields written and `updated_at`; each resolving action → appeal status,
  `resolved_by`/`resolved_at`, the audit row's kind and `appeal`; a refusal writes nothing.
- Races (`transaction=True`, `run_together`): two appeals at once → one `Appeal`, one `AlreadyAppealed`; an appeal and a
  Mark FALSE at once serialise on the post lock; two Restores → one restore, one refusal.
- Pipeline interplay: a post restored to `pending` is due and gets checked (and is kicked when the kick is on); one
  restored into review isn't in the queue; a label-appeal post is ignored by `apply_pipeline_result`;
  `pipeline_had_its_say` in `test_routing.py`.
- API: 401; 403 `email_unverified` (not counted); 404 malformed / unknown / deleted; 400 reason over 500 code points
  (500 emoji pass); 403 `not_author`; 409 `already_appealed`; 409 `not_appealable` for pending, published,
  verified_true and under review (including `pre_review_status=verified_false`); 201 body (24 keys, `status`,
  `can_appeal` false, `appeal_status` open, for a label and a removal appeal); 405 for GET **without using the
  allowance**; the 6th request in a day is 429 (the real 6 requests); the query count of a 201.
- Post object per viewer (author / other / visitor) across lists and the detail: `can_appeal`, `appeal_status`,
  `removal_reason` (latest `removed` row; blank; `""` after a restore; never to others); the 24-key pin; **unchanged
  query counts** for Recent, Following, profile, bookmarks and detail with appeals and removal rows present.
- Profile: the owner sees their removed posts (with `post_type`), others and visitors don't, a repost of someone
  else's removed post stays a stub; query counts.
- Admin: the queue holds removal appeals (and not resolved or deleted ones); the appeal filter; the Reason column;
  waiting and default order; constant queries at 5 and 100 rows with appeals; Restore and Keep removed through the
  admin client (confirmation "after", messages, skips with reasons); buttons per rules; Escalate on a removal appeal;
  the inline and `AppealAdmin` per role (visitor, moderator, senior, superuser), 403 for writes.

**Frontend:** `appeals-api`, `messages`, `AppealModal` (validation, lock, every outcome, focus), `AppealButton`
(author only, unverified, modal kept, one button), `AppealOutcome` (each status combination), `RemovedPostCard`
(public / author, reason or none, button / chip / outcome, the chip surviving a re-render with a new post object),
`PostDetail` (removed for each viewer with the `<h1>` and wording kept, the button on a FALSE post, outcomes including
**a restored opinion**, `patch`), `VerdictBlock`, `PostCard` (the removed guard), `FeedList` / `ProfilePosts` (a
removed item per viewer), `post-card-props`.

**E2E (`e2e/appeals.spec.ts`, no sign-up):** a seeded author logs in, posts a fact, `setPostState(…,
"verified_false")`, opens the post, Request another look → Send → UNDER REVIEW + APPEAL PENDING; `resolveAppeal`
(Mark verified through the service with a seeded moderator) → reload → VERIFIED and "A moderator reversed the
decision". A second test: the author's post removed through the service (with a reason) shows on their profile with
the reason and the button; the appeal is sent and the card shows APPEAL PENDING.

## Verification (end to end)

- Backend (venv activated in every call): `ruff check .`, `ruff format --check .`, `python manage.py makemigrations
  --check --dry-run`, `python manage.py check`, `pytest` (all), the Part 11 set, the threaded tests 10 runs in a row;
  migrations applied, rolled back to `moderation 0002` and applied again on a database holding appeals but no
  `kept_removed` row (the groups keep 0002's permissions after the rollback).
- Frontend: `npm run lint`, `lint:tokens`, `typecheck`, `format:check`, `npm test`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm
  run build`, `npm run test:e2e` (and once with `CI=1`).
- Mutation checks (backend and frontend), at least: no post lock / no appeal lock, the duplicate check gone, any
  status appealable, the label appeal not entering review, a removal appeal changing the status, `original_moderator`
  from `moderated_by`, the rule not applied / applied to seniors or to Escalate, Restore always to `pending` / never
  to review / keeping `pre_removal_status` or `escalated_at`, Keep removed leaving the flag, Remove not closing the
  label appeal, the audit row without `appeal`, the queue without removal appeals, `removal_reason` shown to others or
  from the wrong row, `appeal_status` to non-authors, `can_appeal` ignoring the status, the profile showing removed
  posts to others, the button for non-authors, the modal unlocked while sending.
- Browser (headless Chromium, 1280 and 390 px, screenshots looked at): the FALSE post's button, modal, chip and
  outcome; the removed post for the author (page and profile) and for a visitor; the admin queue with both appeal
  kinds, a Restore with its confirmation, the inline and `AppealAdmin`.
- `docs/test-command.md` Part 11: the Linux blocks extracted by script and run verbatim against live Django, output
  diffed with the doc; the PowerShell twins written but not run (no PowerShell here).

## Stop conditions

- A required test, lint or type check fails for a reason not understood after one investigation.
- A list's query count grows, or the queue's count isn't constant with appeals.
- `merge_flag`, the Part 10 checks or the pipeline queue would need a semantic change beyond this plan.
- A decision above turns out to conflict with the code (ask before changing course).
- Context or usage running low: checkpoint HANDOFF and stop.

## Follow-ups to record (not done here)

- **11B:** reputation hooks in `file_appeal`'s outcomes and in `_perform` (Restore reverses `post_removed` for the
  author and reposters; a label appeal overturned reverses `fact_false`; Remove on a label appeal records
  `post_removed`), the negative ledger rows' appeal link.
- **13:** `appeal_resolved` notifications from `_perform` when `effect.appeal_status` is set (same transaction).
- **14:** appeals in the data export; account deletion cascades them.
- **16:** whether a deleted post's open appeal should be closed; the appeal throttle with real usage.
