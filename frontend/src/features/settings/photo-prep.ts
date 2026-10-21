/**
 * Getting a chosen file ready to upload as a profile photo (ARCHITECTURE §4e, §10; Part 14B).
 *
 * Every file is decoded and drawn again in the browser: the centre square, at most 1024 px, saved
 * as a JPEG (quality 0.9) on a white background. Canvas output carries no EXIF, so the location and
 * camera data of the original never leave the device, and a phone photo of 12 MB becomes well
 * under 1 MB. The server decodes and re-encodes whatever it receives anyway (its limits are 5 MB,
 * 25 MP and 128 px), so this is for the person's benefit, not the server's safety.
 *
 * The browser checks run in this order: the type, the size (up to 20 MB), whether the browser can
 * decode it at all, and the short side (at least 128 px). The pixels and the canvas are injected
 * (`PhotoDeps`) because jsdom has neither `createImageBitmap` nor a canvas.
 */

export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const MAX_ORIGINAL_BYTES = 20 * 1024 * 1024;
export const MIN_SIDE = 128;
export const MAX_OUTPUT_SIDE = 1024;
export const OUTPUT_TYPE = "image/jpeg";
export const OUTPUT_QUALITY = 0.9;

export type PhotoProblem = "type" | "too_big" | "unreadable" | "too_small";

/** The file can't be used; `problem` says why (the uploader words it). */
export class PhotoPrepError extends Error {
  readonly problem: PhotoProblem;

  constructor(problem: PhotoProblem) {
    super(`The photo can't be used: ${problem}`);
    this.name = "PhotoPrepError";
    this.problem = problem;
  }
}

/** A decoded picture (an `ImageBitmap` is one). */
export interface Bitmap {
  readonly width: number;
  readonly height: number;
  close(): void;
}

/** A square drawing surface (a canvas). */
export interface Surface {
  fillWhite(): void;
  /** Draws the `side` x `side` square at (`left`, `top`) of `bitmap` over the whole surface. */
  drawSquare(bitmap: Bitmap, left: number, top: number, side: number): void;
  toBlob(type: string, quality: number): Promise<Blob | null>;
}

export interface PhotoDeps {
  /** Decodes `file` with its EXIF orientation applied; rejects when the browser can't read it. */
  decode(file: Blob): Promise<Bitmap>;
  /** A new `size` x `size` surface. */
  surface(size: number): Surface;
}

export interface PreparedPhoto {
  /** The JPEG to upload. */
  blob: Blob;
  /** Its width and height in pixels. */
  side: number;
}

/** The real thing: `createImageBitmap` and a canvas. Only called in a browser. */
export function browserDeps(): PhotoDeps {
  return {
    decode: (file) => createImageBitmap(file, { imageOrientation: "from-image" }),
    surface: (size) => {
      const canvas = document.createElement("canvas");
      canvas.width = size;
      canvas.height = size;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("no 2d canvas");
      return {
        fillWhite() {
          context.fillStyle = "white";
          context.fillRect(0, 0, size, size);
        },
        drawSquare(bitmap, left, top, side) {
          context.imageSmoothingQuality = "high";
          context.drawImage(bitmap as ImageBitmap, left, top, side, side, 0, 0, size, size);
        },
        toBlob: (type, quality) => new Promise((resolve) => canvas.toBlob(resolve, type, quality)),
      };
    },
  };
}

function isAccepted(type: string): boolean {
  return (ACCEPTED_TYPES as readonly string[]).includes(type);
}

/**
 * Checks `file` and returns the square JPEG to upload, or throws a `PhotoPrepError`.
 * The centre square is taken from the upright picture, so a portrait photo loses its top and
 * bottom, and a landscape one its sides, as the server does.
 */
export async function preparePhoto(
  file: Blob,
  deps: PhotoDeps = browserDeps(),
): Promise<PreparedPhoto> {
  if (!isAccepted(file.type)) throw new PhotoPrepError("type");
  if (file.size > MAX_ORIGINAL_BYTES) throw new PhotoPrepError("too_big");

  let bitmap: Bitmap;
  try {
    bitmap = await deps.decode(file);
  } catch {
    throw new PhotoPrepError("unreadable");
  }

  try {
    const { width, height } = bitmap;
    const side = Math.min(width, height);
    if (side < MIN_SIDE) throw new PhotoPrepError("too_small");

    const output = Math.min(side, MAX_OUTPUT_SIDE);
    const surface = deps.surface(output);
    surface.fillWhite();
    surface.drawSquare(
      bitmap,
      Math.floor((width - side) / 2),
      Math.floor((height - side) / 2),
      side,
    );
    const blob = await surface.toBlob(OUTPUT_TYPE, OUTPUT_QUALITY);
    if (!blob) throw new PhotoPrepError("unreadable");
    return { blob, side: output };
  } catch (error) {
    if (error instanceof PhotoPrepError) throw error;
    throw new PhotoPrepError("unreadable");
  } finally {
    bitmap.close();
  }
}
