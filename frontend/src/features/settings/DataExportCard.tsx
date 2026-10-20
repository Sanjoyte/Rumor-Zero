"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { ApiError } from "@/lib/api/client";
import { SETTINGS_MESSAGES } from "./messages";
import { exportFilename, fetchExport, saveJsonFile } from "./settings-api";

/**
 * Settings, "Your data" (Stitch c2 "Sovereign Data Export", without the archive and the Merkle
 * proofs): downloads everything stored about the account as one JSON file. The server limits it to
 * 10 downloads an hour.
 */
export function DataExportCard({ username }: { username: string }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function download() {
    if (busy) return;
    setBusy(true);
    try {
      const data = await fetchExport();
      saveJsonFile(data, exportFilename(username));
    } catch (error) {
      const throttled = error instanceof ApiError && error.status === 429;
      toast.show(throttled ? SETTINGS_MESSAGES.exportThrottled : SETTINGS_MESSAGES.exportFailed, {
        tone: "error",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-space-md rounded-lg border border-outline-variant/30 bg-surface-container-lowest p-space-md">
      <div className="max-w-xl">
        <h3 className="font-body-sm text-body-sm font-semibold text-on-surface">
          Download your data
        </h3>
        <p className="mt-0.5 font-body-sm text-body-sm text-outline">
          One JSON file with your profile, posts, comments, likes, follows, bookmarks, reposts,
          reports, appeals, credibility history and notifications.
        </p>
      </div>
      <Button variant="secondary" onClick={() => void download()} loading={busy}>
        <Icon name="download" size="sm" />
        Download your data (JSON)
      </Button>
    </div>
  );
}
