"""The mixed timeline against real rows: key order and ties, the cursor filters, the two-sided
slice, a walk while items arrive or change, and a seeded brute-force comparison with a reference
written independently of `take_page` (the rule is stated in `social.timeline`'s docstring)."""

import random
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.posts.models import Post
from apps.social import timeline
from apps.social.models import Repost
from apps.social.tests.factories import (
    FollowFactory,
    PostFactory,
    RepostFactory,
    VerifiedUserFactory,
)
from apps.social.timeline import POST, REPOST, ZERO_UUID, Key

pytestmark = pytest.mark.django_db


# ---------- helpers ----------


def all_keys(posts=None, reposts=None):
    """Every item as a `Key`, newest first, built in Python from the rows (the reference)."""
    posts = Post.objects.visible() if posts is None else posts
    reposts = Repost.objects.all() if reposts is None else reposts
    keys = [Key(p.created_at, POST, p.pk, ZERO_UUID) for p in posts]
    keys += [Key(r.created_at, REPOST, r.post_id, r.user_id) for r in reposts]
    return sorted(keys, reverse=True)


def reference_pages(items, size, *, dedupe=True):
    """The rule, written the long way: take a window, keep the first row of each post up to
    `size`, consume what was hidden, and start the next page after the consumed rows."""
    pages, i = [], 0
    while i < len(items):
        window = items[i : i + (2 * size if dedupe else size)]
        kept, seen, consumed = [], set(), 0
        for row in window:
            if dedupe and row.ref in seen:
                consumed += 1
                continue
            if len(kept) == size:
                break
            seen.add(row.ref)
            kept.append(row)
            consumed += 1
        pages.append(kept)
        i += consumed
    return pages


def walk(size, *, dedupe=True, between=None, posts=None, reposts=None):
    """Page through the live tables; `between(n)` runs before the n-th fetch (n from 0)."""
    cursor, pages, nxt = None, [], None
    while True:
        if between is not None:
            between(len(pages))
        kept, nxt = timeline.page(
            Post.objects.visible() if posts is None else posts(),
            Repost.objects.all() if reposts is None else reposts(),
            size=size,
            cursor=cursor,
            dedupe=dedupe,
        )
        pages.append((kept, nxt))
        if nxt is None:
            return pages
        assert len(pages) < 2000, "the walk does not end"
        cursor = timeline.decode_token(nxt.token())  # through the codec, as a client would


def instants(n, step=1):
    base = timezone.now().replace(microsecond=123456) - timedelta(hours=1)
    return [base + timedelta(seconds=step * i) for i in range(n)]


# ---------- order and ties ----------


def test_a_repost_sorts_before_a_post_of_the_same_instant_then_by_post_then_reposter():
    when = timezone.now() - timedelta(minutes=5)
    p1, p2 = PostFactory(created_at=when), PostFactory(created_at=when)
    u1, u2 = VerifiedUserFactory(), VerifiedUserFactory()
    RepostFactory(user=u1, post=p1, created_at=when)
    RepostFactory(user=u2, post=p1, created_at=when)
    RepostFactory(user=u1, post=p2, created_at=when)
    (page,) = [kept for kept, _ in walk(50, dedupe=False)]
    assert [(k.kind) for k in page] == [REPOST, REPOST, REPOST, POST, POST]
    assert page == all_keys()
    assert [k.ref for k in page[:3]] == sorted([p1.pk, p1.pk, p2.pk], reverse=True)


def test_ten_items_on_one_instant_page_cleanly():
    when = timezone.now() - timedelta(minutes=5)
    users = VerifiedUserFactory.create_batch(5)
    posts = [PostFactory(created_at=when) for _ in range(5)]
    for user, post in zip(users, posts, strict=True):
        RepostFactory(user=user, post=post, created_at=when)
    seen = [k for kept, _ in walk(3, dedupe=False) for k in kept]
    assert seen == all_keys() and len(seen) == 10 and len(set(seen)) == 10


def test_the_cursor_filters_select_exactly_the_keys_below_the_cursor():
    """For every item as the cursor, the union is the Python list of keys below it."""
    rng = random.Random(7)
    moments = instants(3)
    users = VerifiedUserFactory.create_batch(4)
    posts = [PostFactory(created_at=rng.choice(moments)) for _ in range(9)]
    for user in users:
        for post in rng.sample(posts, 4):
            RepostFactory(user=user, post=post, created_at=rng.choice(moments))
    everything = all_keys()
    assert len(everything) == 9 + 16
    for cursor in everything:
        kept, nxt = timeline.page(
            Post.objects.visible(),
            Repost.objects.all(),
            size=100,
            cursor=cursor,
            dedupe=False,
        )
        assert kept == [k for k in everything if k < cursor]
        assert nxt is None


def test_both_sides_carry_the_redundant_less_or_equal_that_lets_the_index_serve_a_deep_page():
    """`created_at < t OR (…)` alone can't become an index condition, so a deep page would scan
    from the newest row (`EXPLAIN`, HANDOFF). The plain `<=` has no effect on the rows returned;
    only the SQL shows it, so this test reads the SQL."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    for kind in (POST, REPOST):
        cursor = Key(
            timezone.now(), kind, uuid.uuid4(), ZERO_UUID if kind == POST else uuid.uuid4()
        )
        with CaptureQueriesContext(connection) as captured:
            timeline.page(
                Post.objects.visible(), Repost.objects.all(), size=5, cursor=cursor, dedupe=True
            )
        sql = captured.captured_queries[-1]["sql"]
        assert '"posts_post"."created_at" <=' in sql, kind
        if kind == REPOST:  # a post cursor excludes same-instant reposts: a plain `<` is right
            assert '"social_repost"."created_at" <=' in sql


def test_each_side_is_sliced_separately_so_a_long_side_cannot_hide_a_short_one():
    moments = instants(60)
    old_posts = [PostFactory(created_at=moments[i]) for i in range(40)]  # old and many
    for i, user in enumerate(VerifiedUserFactory.create_batch(3)):  # new and few
        RepostFactory(user=user, post=old_posts[i], created_at=moments[50 + i])
    pages = walk(2)
    assert [kept for kept, _ in pages] == reference_pages(all_keys(), 2)
    assert [k.kind for k in pages[0][0]] == [REPOST, REPOST]  # the new, short side comes first
    # the 40 old posts are far more than one fetch (5 rows): the walk still reaches all of them.
    # A repost and its original are 50 rows apart, never on one page, so nothing is hidden.
    assert sum(len(kept) for kept, _ in pages) == 43


def test_a_reposted_post_that_is_no_longer_visible_still_has_its_repost_item():
    post = PostFactory(created_at=timezone.now() - timedelta(hours=2))
    RepostFactory(post=post)
    post.status = "removed"
    post.save()
    assert [k.kind for k in all_keys()] == [REPOST]
    ((kept, _),) = walk(5)
    assert [k.kind for k in kept] == [REPOST]


# ---------- cursors and changes during a walk ----------


def seed_mixed(n_posts=6, n_reposts=4):
    """Posts at even instants, oldest first in the list; the newest `n_reposts` posts each get a
    repost one instant after them."""
    moments = instants(2 * n_posts + 1, step=10)
    users = VerifiedUserFactory.create_batch(n_reposts)
    posts = [PostFactory(created_at=moments[2 * i]) for i in range(n_posts)]
    for i, user in enumerate(users):
        RepostFactory(
            user=user, post=posts[n_posts - 1 - i], created_at=moments[2 * (n_posts - 1 - i) + 1]
        )
    return posts, users


def test_a_whole_walk_equals_the_reference_for_every_page_size():
    seed_mixed(12, 8)
    for size in (1, 2, 3, 5, 7, 20):
        pages = walk(size)
        assert [kept for kept, _ in pages] == reference_pages(all_keys(), size)
        assert pages[-1][1] is None


def test_the_cursor_row_deleted_between_pages_changes_nothing_for_the_next_page():
    seed_mixed(10, 5)
    _, first_next = timeline.page(
        Post.objects.visible(), Repost.objects.all(), size=3, cursor=None, dedupe=False
    )
    if first_next.kind == POST:
        Post.objects.filter(pk=first_next.ref).delete()
    else:
        Repost.objects.filter(post_id=first_next.ref, user_id=first_next.by).delete()
    kept, _ = timeline.page(
        Post.objects.visible(), Repost.objects.all(), size=3, cursor=first_next, dedupe=False
    )
    assert kept == [k for k in all_keys() if k < first_next][:3]


def test_new_posts_and_reposts_arriving_during_a_walk_never_enter_or_shift_it():
    posts, users = seed_mixed(8, 4)
    snapshot = [kept for kept, _ in walk(2)]
    fan = iter(VerifiedUserFactory.create_batch(60))
    added = []

    def arrive(n):
        if n == 0:
            return
        added.append(PostFactory(created_at=timezone.now()))
        RepostFactory(user=next(fan), post=posts[0], created_at=timezone.now())  # an unseen post
        RepostFactory(user=next(fan), post=posts[-1], created_at=timezone.now())  # a seen post

    live = [kept for kept, _ in walk(2, between=arrive)]
    assert live == snapshot
    assert added  # the walk really had pages after the first


def test_undoing_an_unseen_repost_removes_it_and_redoing_a_seen_one_does_not_repeat_it():
    posts, users = seed_mixed(8, 4)
    everything = all_keys()
    seen = []
    cursor = None
    undone = None

    for n in range(100):
        if n == 1:
            # drop the last (oldest) repost from the world: it must not be shown
            undone = next(k for k in reversed(everything) if k.kind == REPOST)
            Repost.objects.filter(post_id=undone.ref, user_id=undone.by).delete()
            # and redo the first repost shown (it moves to the top, above the cursor)
            first = next(k for k in seen if k.kind == REPOST)
            Repost.objects.filter(post_id=first.ref, user_id=first.by).delete()
            RepostFactory(user_id=first.by, post_id=first.ref, created_at=timezone.now())
        kept, nxt = timeline.page(
            Post.objects.visible(), Repost.objects.all(), size=2, cursor=cursor, dedupe=True
        )
        seen += kept
        if nxt is None:
            break
        cursor = nxt
    assert undone not in seen
    assert len(seen) == len(set(seen))
    assert all(a > b for a, b in zip(seen, seen[1:], strict=False))  # strictly descending


# ---------- the seeded brute force ----------

POOL_SECONDS = (0, 0, 1, 1, 2, 3)


def make_world(rng):
    """A random world with ties everywhere: `me`, the people `me` follows and a stranger."""
    me = VerifiedUserFactory()
    followed = VerifiedUserFactory.create_batch(rng.randint(3, 5))
    stranger = VerifiedUserFactory()
    for person in followed:
        FollowFactory(follower=me, following=person)
    people = [me, *followed, stranger]
    base = timezone.now().replace(microsecond=654321) - timedelta(hours=3)

    def when():
        return base + timedelta(seconds=rng.choice(POOL_SECONDS))

    shapes = [
        {},
        {"fact": True},
        {"verified_pipeline": True},
        {"moderator_verdict": True},
        {"removed": True},
        {"deleted": True},
    ]
    posts = Post.objects.bulk_create(
        [
            PostFactory.build(
                author=rng.choice(people),
                created_at=when(),
                **rng.choices(shapes, weights=[60, 8, 10, 6, 8, 8])[0],
            )
            for _ in range(rng.randint(30, 60))
        ]
    )
    pairs = {}
    for _ in range(rng.randint(30, 60)):
        post, user = rng.choice(posts), rng.choice(people)
        if post.author_id != user.pk:
            pairs[(user.pk, post.pk)] = RepostFactory.build(user=user, post=post, created_at=when())
    Repost.objects.bulk_create(list(pairs.values()))
    return me, [me, *followed]


def following_sides(circle):
    ids = [u.pk for u in circle]
    return (
        lambda: Post.objects.visible().filter(author_id__in=ids),
        lambda: Repost.objects.filter(user_id__in=ids),
    )


@pytest.mark.parametrize("seed", range(50))
def test_every_walk_equals_the_reference_whatever_the_page_size(seed):
    rng = random.Random(seed)
    me, circle = make_world(rng)
    posts, reposts = following_sides(circle)
    everything = all_keys(posts(), reposts())
    assert len(everything) > 10
    for size in (1, 2, 3, 5):
        pages = walk(size, posts=posts, reposts=reposts)
        assert [kept for kept, _ in pages] == reference_pages(everything, size), (seed, size)
        assert pages[-1][1] is None
        flat = [k for kept, _ in pages for k in kept]
        assert all(len(kept) <= size for kept, _ in pages)
        assert all(len(kept) >= 1 for kept, _ in pages)  # every page advances
        assert all(a > b for a, b in zip(flat, flat[1:], strict=False))
    # a profile list never dedupes and its pages are full
    for size in (2, 5):
        pages = walk(size, dedupe=False, posts=posts, reposts=reposts)
        assert [kept for kept, _ in pages] == reference_pages(everything, size, dedupe=False)
        assert all(len(kept) == size for kept, _ in pages[:-1])


def mutate(rng, state):
    """One random change to the live tables; returns nothing."""
    people, posts = state["people"], state["posts"]
    choice = rng.choice(["post", "repost", "undo", "redo", "delete"])
    now = timezone.now()
    if choice == "post":
        posts.append(PostFactory(author=rng.choice(people), created_at=now))
    elif choice == "repost":
        post, user = rng.choice(posts), rng.choice(people)
        if post.author_id != user.pk and not Repost.objects.filter(user=user, post=post).exists():
            RepostFactory(user=user, post=post, created_at=now)
    elif choice in ("undo", "redo"):
        rows = list(Repost.objects.order_by("pk"))
        row = rng.choice(rows) if rows else None
        if row is not None:
            user_id, post_id = row.user_id, row.post_id
            row.delete()
            if choice == "redo":
                RepostFactory(user_id=user_id, post_id=post_id, created_at=now)
    else:
        Post.objects.filter(pk=rng.choice(posts).pk).update(deleted_at=now)


@pytest.mark.parametrize("seed", range(50))
def test_a_walk_stays_sound_while_the_world_changes(seed):
    rng = random.Random(1000 + seed)
    me, circle = make_world(rng)
    posts, reposts = following_sides(circle)
    state = {"people": circle, "posts": list(Post.objects.filter(author__in=circle))}
    size = rng.choice([1, 2, 3, 5])
    start = all_keys(posts(), reposts())

    def change(n):
        if n:
            for _ in range(rng.randint(0, 2)):
                mutate(rng, state)

    pages = walk(size, between=change, posts=posts, reposts=reposts)
    flat = [k for kept, _ in pages for k in kept]
    assert len(pages) <= len(start) + 1  # the walk ends within N + 1 requests
    assert all(a > b for a, b in zip(flat, flat[1:], strict=False)), "keys must strictly descend"
    assert len(set(flat)) == len(flat)
    for kept, _ in pages:
        assert len(kept) <= size
        assert len({k.ref for k in kept}) == len(kept)  # no post twice on a page
    # Every item that was there at the start and still is must be shown, unless an item of the
    # same post with a larger key was shown on the page that consumed it.
    survivors = set(all_keys(posts(), reposts())) & set(start)
    shown = set(flat)
    upper = None  # the cursor that opened the page
    ranges = []
    for kept, nxt in pages:
        ranges.append((upper, nxt, kept))
        upper = nxt
    for key in survivors - shown:
        owner = next(
            kept
            for top, bottom, kept in ranges
            if (top is None or key < top) and (bottom is None or key >= bottom)
        )
        assert any(k.ref == key.ref and k > key for k in owner), (seed, key)


# ---------- the same walk through the API (cache on and off) ----------


def api_items(body):
    return [
        (
            i["kind"],
            i["post"]["id"],
            (i["reposted_by"] or {}).get("id"),
            i["activity_at"],
            bool(i["post"].get("unavailable")),
        )
        for i in body["results"]
    ]


def expected_items(keys, visible_ids):
    from apps.posts.serializers import iso

    return [
        (
            "post" if k.kind == POST else "repost",
            str(k.ref),
            None if k.kind == POST else str(k.by),
            iso(k.at),
            k.kind == REPOST and k.ref not in visible_ids,
        )
        for k in keys
    ]


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("size", [None, 2, 5])
def test_the_feed_endpoint_walks_like_the_reference_with_and_without_the_cache(
    auth_client, seed, size
):
    rng = random.Random(500 + seed)
    me, circle = make_world(rng)
    posts, reposts = following_sides(circle)
    everything = all_keys(posts(), reposts())
    visible = set(Post.objects.visible().values_list("pk", flat=True))
    client = auth_client(me)
    # size None: the defaults, so the first page is the cached one (asked twice: miss, then hit)
    effective = size or 20
    pages = reference_pages(everything, effective)
    params = {"page_size": size} if size else {}
    cursor, got = None, []
    for i in range(len(pages) + 2):
        query = dict(params)
        if cursor:
            query["cursor"] = cursor
        body = client.get("/api/v1/feed/", query).json()
        if i == 0 and size is None:
            assert api_items(client.get("/api/v1/feed/").json()) == api_items(body)  # a cache hit
        got.append(api_items(body))
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert cursor is None
    assert got == [expected_items(kept, visible) for kept in pages]
