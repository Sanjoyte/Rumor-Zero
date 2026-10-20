"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Checkbox";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { Textarea } from "@/components/ui/Textarea";
import { Toggle } from "@/components/ui/Toggle";
import type { FactQuota, PostType } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { countCharacters } from "@/lib/format";
import { type Draft, newRow } from "./draft";
import { confirmationText, EMERGENCY_COPY, emergencyReasonText } from "./emergency-copy";
import { type ComposerFailure, POST_MESSAGES } from "./messages";
import { quotaLine, formatNextSlot } from "./quota";
import { SourceFields, sourceInputId } from "./SourceFields";
import { checkSourceRows } from "./sources";

export const MAX_CONTENT = 500;
const CONTENT_ID = "composer-content";
const CONFIRM_ID = "composer-emergency-confirm";
const CONFIRM_ERROR_ID = "composer-emergency-confirm-error";

export interface ComposerSubmit {
  content: string;
  postType: PostType;
  sources: string[];
  /** The row behind each source sent: a server error at `sources.N` belongs to `rowIds[N]`. */
  rowIds: string[];
  /**
   * Send `is_emergency: true` (Part 11C): only for a fact whose toggle is on while the quota says
   * emergencies are allowed (the draft outlives the modal, and a refetched quota can say no).
   */
  emergency: boolean;
}

export interface ComposerModalProps {
  open: boolean;
  onClose: () => void;
  draft: Draft;
  onDraftChange: (patch: Partial<Draft>) => void;
  /** True while a post is on its way (the modal stays open until the answer: "Posting…"). */
  submitting: boolean;
  /** The last failure that isn't about one field (quota, throttle, network, …). */
  failure: ComposerFailure | null;
  quota: FactQuota | null;
  verified: boolean;
  /** Resolves to null on success, or the failure; field errors are placed under their fields. */
  onSubmit: (submit: ComposerSubmit) => Promise<ComposerFailure | null>;
  /** Clock and time zone for "next at 14:05"; tests pass fixed ones. */
  now?: Date;
  timeZone?: string;
}

interface Errors {
  content?: string;
  postType?: string;
  /** The list rule from the server ("You can add up to 5 sources."). */
  sources?: string;
  /** The emergency confirmation, unticked at submit. */
  confirm?: string;
  /** By source row id. */
  rows: Record<string, string>;
}

const NO_ERRORS: Errors = { rows: {} };

function hasErrors(errors: Errors): boolean {
  return Boolean(
    errors.content ||
    errors.postType ||
    errors.sources ||
    errors.confirm ||
    Object.keys(errors.rows).length > 0,
  );
}

const TYPE_OPTIONS = [
  { value: "opinion" as const, label: "Opinion", icon: "format_quote" },
  { value: "fact" as const, label: "Fact", icon: "fact_check" },
];

const TYPE_HINT: Record<string, string> = {
  none: "Choose one to continue",
  opinion: "Opinions are published at once",
  fact: "Fact posts are checked after you post",
};

/**
 * The composer (Stitch b2): text with a 500-character counter, a required Opinion/Fact choice,
 * up to five optional sources on a fact post, the rolling-24-hour fact allowance and the submit
 * button. The submit button stays enabled: clicking it shows every problem and focuses the first.
 * The draft and the request live in `ComposerProvider`, so closing the modal never loses either.
 *
 * A fact can be an emergency (Part 11C, b2's toggle with its copy rewritten): the toggle is disabled
 * with the reason until the allowance says yes; on, it shows the warning box and a required
 * confirmation, and the button reads "Post emergency, will be checked".
 */
export function ComposerModal({
  open,
  onClose,
  draft,
  onDraftChange,
  submitting,
  failure,
  quota,
  verified,
  onSubmit,
  now,
  timeZone,
}: ComposerModalProps) {
  const [errors, setErrors] = useState<Errors>(NO_ERRORS);
  const [notice, setNotice] = useState<ComposerFailure | null>(null);
  const typeRef = useRef<HTMLDivElement>(null);
  const pendingFocus = useRef<string | null>(null);
  const emergencyHintId = useId();

  // A new row (or the row before a removed one) takes focus once it is on the page.
  useEffect(() => {
    if (pendingFocus.current) {
      document.getElementById(sourceInputId(pendingFocus.current))?.focus();
      pendingFocus.current = null;
    }
  }, [draft.rows]);

  const unverified = !verified || failure?.kind === "unverified";
  const locked = submitting || unverified;
  const isFact = draft.postType === "fact";
  // Disabled until the allowance has loaded and says yes; the provider turns a toggle the
  // allowance no longer allows off (Part 11C). An answer without the block (a backend older than
  // the page) reads as "not allowed".
  const eligibility = quota?.emergency;
  const emergencyAllowed = eligibility?.allowed === true;
  const emergencyOn = isFact && draft.emergency && emergencyAllowed;
  const emergencyHint =
    eligibility && !emergencyAllowed ? emergencyReasonText(eligibility, { now, timeZone }) : "";
  const banner = notice ?? failure;
  const showBanner =
    banner !== null &&
    banner.kind !== "unverified" &&
    (banner.kind !== "fields" || hasErrors(errors));
  const line = quotaLine(quota, { now, timeZone });

  function setContent(content: string) {
    onDraftChange({ content });
    if (errors.content) setErrors((e) => ({ ...e, content: undefined }));
  }

  function setPostType(postType: PostType) {
    onDraftChange({ postType });
    setNotice(null);
    setErrors((e) => ({ ...e, postType: undefined }));
  }

  function setEmergency(on: boolean) {
    onDraftChange({ emergency: on, confirmed: on ? draft.confirmed : false });
    setNotice(null);
    setErrors((e) => ({ ...e, confirm: undefined }));
  }

  function setConfirmed(confirmed: boolean) {
    onDraftChange({ confirmed });
    if (errors.confirm) setErrors((e) => ({ ...e, confirm: undefined }));
  }

  function setRow(id: string, text: string) {
    onDraftChange({ rows: draft.rows.map((row) => (row.id === id ? { ...row, text } : row)) });
    if (errors.rows[id] || errors.sources) {
      setErrors((e) => {
        const rows = { ...e.rows };
        delete rows[id];
        return { ...e, rows, sources: undefined };
      });
    }
  }

  function blurRow(id: string) {
    const row = draft.rows.find((r) => r.id === id);
    if (!row) return;
    const message = row.text.trim() === "" ? undefined : checkSourceRows(draft.rows).errors[id];
    setErrors((e) => {
      const rows = { ...e.rows };
      if (message) rows[id] = message;
      else delete rows[id];
      return { ...e, rows };
    });
  }

  function addRow() {
    const row = newRow();
    pendingFocus.current = row.id;
    onDraftChange({ rows: [...draft.rows, row] });
  }

  function removeRow(id: string) {
    const index = draft.rows.findIndex((row) => row.id === id);
    pendingFocus.current = draft.rows[Math.max(index - 1, 0)]?.id ?? null;
    onDraftChange({ rows: draft.rows.filter((row) => row.id !== id) });
    setErrors((e) => {
      const rows = { ...e.rows };
      delete rows[id];
      return { ...e, rows };
    });
  }

  /** What the quota already says: don't send a fact post that is sure to be refused. */
  function quotaRefusal(): ComposerFailure | null {
    if (!quota) return null;
    const fields = { sourceRows: {} };
    if (quota.limit === 0) {
      return { kind: "paused", message: POST_MESSAGES.quotaPaused, fields };
    }
    if (quota.remaining > 0) return null;
    const next = quota.next_slot_at
      ? ` You can post another ${formatNextSlot(quota.next_slot_at, { now, timeZone })}.`
      : "";
    return {
      kind: "quota",
      message: `You've used all ${quota.limit} of your fact posts for the last 24 hours.${next}`,
      fields,
    };
  }

  function focusFirstProblem(next: Errors) {
    if (next.content) return document.getElementById(CONTENT_ID)?.focus();
    if (next.postType) {
      return typeRef.current?.querySelector<HTMLElement>("[role='radio']")?.focus();
    }
    if (next.confirm) return document.getElementById(CONFIRM_ID)?.focus();
    const firstRow = draft.rows.find((row) => next.rows[row.id]);
    if (firstRow) document.getElementById(sourceInputId(firstRow.id))?.focus();
  }

  async function submit() {
    if (locked) return;
    const next: Errors = { rows: {} };
    const content = draft.content.trim();
    if (!content) next.content = "Write something first.";
    else if (countCharacters(content) > MAX_CONTENT) {
      next.content = `Keep it to ${MAX_CONTENT} characters.`;
    }
    if (!draft.postType) next.postType = "Choose Opinion or Fact.";
    let sources: string[] = [];
    let rowIds: string[] = [];
    if (isFact) {
      const checked = checkSourceRows(draft.rows);
      next.rows = checked.errors;
      sources = checked.sources;
      rowIds = checked.rowIds;
    }
    if (emergencyOn && !draft.confirmed) next.confirm = EMERGENCY_COPY.confirmError;
    setErrors(next);
    setNotice(null);
    if (hasErrors(next)) return focusFirstProblem(next);
    if (isFact) {
      const refusal = quotaRefusal();
      if (refusal) return setNotice(refusal);
    }
    const result = await onSubmit({
      content,
      postType: draft.postType!,
      sources,
      rowIds,
      emergency: emergencyOn,
    });
    if (result?.kind === "fields") {
      const rows: Record<string, string> = {};
      for (const [index, message] of Object.entries(result.fields.sourceRows)) {
        const id = rowIds[Number(index)];
        if (id) rows[id] = message;
      }
      const server: Errors = {
        content: result.fields.content,
        postType: result.fields.postType,
        sources: result.fields.sources,
        rows,
      };
      setErrors(server);
      setNotice(result); // "Fix the highlighted fields", while any are still showing
      focusFirstProblem(server);
    } else if (result === null) {
      setErrors(NO_ERRORS);
    }
  }

  const footer = (
    <div className="flex w-full flex-wrap items-center justify-between gap-space-sm">
      {line ? (
        <p className="flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
          <span
            aria-hidden="true"
            className={cn(
              "inline-block h-2 w-2 shrink-0 rounded-full",
              line.tone === "empty" ? "bg-error" : "bg-secondary",
            )}
          />
          <span className={cn(line.tone === "empty" && "text-error")}>
            {line.count && <strong className="font-semibold">{line.count} </strong>}
            {line.text}
            {line.suffix && ` · ${line.suffix}`}
          </span>
        </p>
      ) : (
        <span />
      )}
      <div className="ml-auto flex items-center gap-space-sm">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button loading={submitting} disabled={unverified} onClick={() => void submit()}>
          {submitting ? (
            "Posting…"
          ) : (
            <>
              {isFact && <Icon name="bolt" size="sm" filled />}
              {emergencyOn
                ? EMERGENCY_COPY.submit
                : isFact
                  ? "Post fact, will be checked"
                  : draft.postType
                    ? "Post opinion"
                    : "Post"}
            </>
          )}
        </Button>
      </div>
    </div>
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New post"
      icon="edit_note"
      footer={open ? footer : null}
    >
      {open && (
        <>
          {unverified && (
            <Alert tone="warning" title="Verify your email to post">
              Check your inbox for the link. You can still read everything.
            </Alert>
          )}
          {showBanner && banner && <Alert tone="error">{banner.message}</Alert>}
          <fieldset disabled={locked} className="m-0 min-w-0 space-y-space-lg border-0 p-0">
            <Textarea
              id={CONTENT_ID}
              label="Post text"
              variant="bare"
              maxCount={MAX_CONTENT}
              placeholder="What do you want to say?"
              value={draft.content}
              error={errors.content}
              onChange={(event) => setContent(event.target.value)}
              data-autofocus
            />
            <div ref={typeRef} className="space-y-space-xs">
              <div className="flex items-center justify-between gap-space-sm">
                <span className="shrink-0 font-body-sm text-body-sm font-semibold text-on-surface">
                  Post type
                </span>
                <span className="font-body-sm text-body-sm text-outline">
                  {TYPE_HINT[draft.postType ?? "none"]}
                </span>
              </div>
              <SegmentedControl
                label="Post type"
                options={TYPE_OPTIONS}
                value={draft.postType}
                onChange={setPostType}
              />
              {errors.postType && (
                <p role="alert" className="font-body-sm text-body-sm text-error">
                  {errors.postType}
                </p>
              )}
            </div>
            {isFact && (
              <div className="space-y-space-sm" data-purpose="emergency-section">
                <div className="flex items-start justify-between gap-space-md">
                  <div className="flex items-start gap-space-sm">
                    <Icon name="bolt" filled className="mt-0.5 shrink-0 text-tertiary" />
                    <div>
                      <p className="font-body-sm text-body-sm font-semibold text-on-surface">
                        {EMERGENCY_COPY.title}
                      </p>
                      <p className="mt-0.5 font-body-sm text-body-sm text-outline">
                        {EMERGENCY_COPY.description}
                      </p>
                      {emergencyHint && (
                        <p
                          id={emergencyHintId}
                          className="mt-space-xs font-body-sm text-body-sm text-on-surface-variant"
                        >
                          {emergencyHint}
                        </p>
                      )}
                    </div>
                  </div>
                  <Toggle
                    label={EMERGENCY_COPY.toggleLabel}
                    tone="tertiary"
                    checked={emergencyOn}
                    onCheckedChange={setEmergency}
                    disabled={!emergencyAllowed}
                    aria-describedby={emergencyHint ? emergencyHintId : undefined}
                  />
                </div>
                {emergencyOn && eligibility && (
                  <>
                    <div className="flex items-start gap-space-sm rounded-lg border border-tertiary/30 bg-tertiary/5 p-space-md">
                      <div className="mt-0.5 flex shrink-0 items-center text-tertiary">
                        <Icon name="warning" className="-mr-space-xs" />
                        <Icon name="bolt" size="xs" filled />
                      </div>
                      <p className="font-body-sm text-body-sm text-on-surface-variant">
                        <strong className="font-semibold text-tertiary">
                          {EMERGENCY_COPY.warningTitle}
                        </strong>
                        <br />
                        {EMERGENCY_COPY.warning}
                      </p>
                    </div>
                    <Checkbox
                      id={CONFIRM_ID}
                      label={confirmationText(eligibility.block_days)}
                      checked={draft.confirmed}
                      onChange={(event) => setConfirmed(event.target.checked)}
                      aria-invalid={errors.confirm ? true : undefined}
                      aria-describedby={errors.confirm ? CONFIRM_ERROR_ID : undefined}
                    />
                    {errors.confirm && (
                      <p
                        id={CONFIRM_ERROR_ID}
                        role="alert"
                        className="font-body-sm text-body-sm text-error"
                      >
                        {errors.confirm}
                      </p>
                    )}
                  </>
                )}
              </div>
            )}
            {isFact && (
              <SourceFields
                rows={draft.rows}
                errors={errors.rows}
                listError={errors.sources}
                onChange={setRow}
                onBlur={blurRow}
                onAdd={addRow}
                onRemove={removeRow}
              />
            )}
          </fieldset>
        </>
      )}
    </Modal>
  );
}
