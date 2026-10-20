import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import {
  actorName,
  badgeText,
  NOTIFICATION_MESSAGES,
  notificationHref,
  notificationsErrorMessage,
  unreadLabel,
} from "./messages";
import { BO_ACTOR, makeNotification } from "./test-helpers";

const error = (status: number, code = "x", retryAfter: number | null = null) =>
  new ApiError({ status, code, detail: "", fieldErrors: {}, retryAfter });

describe("notificationsErrorMessage", () => {
  it("says the server is waking for a 503", () => {
    expect(notificationsErrorMessage(error(503))).toBe(NOTIFICATION_MESSAGES.waking);
    expect(notificationsErrorMessage(error(0, "backend_waking"))).toBe(
      NOTIFICATION_MESSAGES.waking,
    );
  });

  it("says how long to wait for a 429", () => {
    expect(notificationsErrorMessage(error(429, "throttled", 30))).toBe(
      "You're going too fast. Try again in a minute.",
    );
    expect(notificationsErrorMessage(error(429, "throttled", 600))).toBe(
      "You're going too fast. Try again in about 10 minutes.",
    );
  });

  it("falls back to the plain failure for anything else", () => {
    expect(notificationsErrorMessage(error(500))).toBe(NOTIFICATION_MESSAGES.listFailed);
    expect(notificationsErrorMessage(new Error("x"))).toBe(NOTIFICATION_MESSAGES.listFailed);
  });
});

describe("counts", () => {
  it("spells the exact number up to 99 and 99+ above", () => {
    expect(badgeText(1)).toBe("1");
    expect(badgeText(99)).toBe("99");
    expect(badgeText(100)).toBe("99+");
    expect(unreadLabel(3)).toBe("3 unread");
    expect(unreadLabel(250)).toBe("99+ unread");
  });
});

describe("notificationHref", () => {
  it("sends a follow to the follower's profile", () => {
    expect(notificationHref(makeNotification({ type: "follow", post: null }))).toBe("/u/bo");
  });

  it("sends a follow from a gone account nowhere", () => {
    expect(
      notificationHref(makeNotification({ type: "follow", post: null, actor: null })),
    ).toBeNull();
  });

  it.each(["like", "comment", "repost", "verdict", "under_review", "removed"] as const)(
    "sends a %s to the post",
    (type) => {
      expect(notificationHref(makeNotification({ type }))).toBe(
        "/p/11111111-1111-4111-8111-111111111111",
      );
    },
  );

  it("sends an item with no post nowhere", () => {
    expect(notificationHref(makeNotification({ post: null }))).toBeNull();
  });
});

describe("actorName", () => {
  it("is the display name, else the handle, else Someone", () => {
    expect(actorName(makeNotification())).toBe("Bo Bell");
    expect(actorName(makeNotification({ actor: { ...BO_ACTOR, display_name: "  " } }))).toBe("@bo");
    expect(actorName(makeNotification({ actor: null }))).toBe("Someone");
  });
});
