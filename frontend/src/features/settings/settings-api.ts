/**
 * The account endpoints behind Settings (ARCHITECTURE §9, Part 14). Ordinary app calls: they send
 * the in-memory access token and get the client's single refresh-and-retry on a 401.
 */
import { api, apiFetch } from "@/lib/api/client";
import type { Me } from "@/lib/api/types";

export const SETTINGS_PATHS = {
  me: "/v1/me/",
  password: "/v1/me/password/",
  export: "/v1/me/export/",
  avatar: "/v1/me/avatar/",
} as const;

/** Any of the three; the server ignores every other key. */
export interface ProfileChanges {
  display_name?: string;
  username?: string;
  bio?: string;
}

/** Saves the changed fields and answers the new `/me` object. */
export function updateProfile(changes: ProfileChanges): Promise<Me> {
  return api.patch<Me>(SETTINGS_PATHS.me, changes);
}

export function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return api.post<void>(SETTINGS_PATHS.password, {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export interface UploadOptions {
  signal?: AbortSignal;
  /** How much of the photo has been sent, 0 to 1. */
  onProgress?: (fraction: number) => void;
}

/**
 * Sets the profile photo (`PUT /me/avatar/`, multipart `file`) and answers the new `/me` object.
 * `photo` is the browser-made JPEG (`photo-prep.ts`); the server decodes and re-encodes it anyway.
 */
export function uploadAvatar(photo: Blob, { signal, onProgress }: UploadOptions = {}): Promise<Me> {
  const body = new FormData();
  body.append("file", photo, "photo.jpg");
  return api.put<Me>(SETTINGS_PATHS.avatar, body, { signal, onUploadProgress: onProgress });
}

/** Takes the photo down (204, also when there was none). */
export function removeAvatar(): Promise<void> {
  return api.del<void>(SETTINGS_PATHS.avatar);
}

/** `{password}` for an account with a password, else `{username}` typed to confirm. */
export type DeleteConfirmation = { password: string } | { username: string };

/** 204 on success. `api.del` takes no body, so this uses `apiFetch` directly. */
export function deleteAccount(confirmation: DeleteConfirmation): Promise<void> {
  return apiFetch<void>(SETTINGS_PATHS.me, { method: "DELETE", body: confirmation });
}

/** Everything the server stores about the account, parsed from the export's JSON. */
export function fetchExport(): Promise<unknown> {
  return api.get<unknown>(SETTINGS_PATHS.export);
}

/** `rumor-zero-<username>-<YYYY-MM-DD>.json`, the server's own name (UTC date). */
export function exportFilename(username: string, now: Date = new Date()): string {
  return `rumor-zero-${username}-${now.toISOString().slice(0, 10)}.json`;
}

/** Hands `data` to the browser as a file download. */
export function saveJsonFile(data: unknown, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoked on the next tick: some browsers start the download after the click returns.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
