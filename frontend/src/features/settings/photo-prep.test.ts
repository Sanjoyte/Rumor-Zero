import { afterEach, describe, expect, it, vi } from "vitest";
import {
  MAX_ORIGINAL_BYTES,
  MAX_OUTPUT_SIDE,
  MIN_SIDE,
  OUTPUT_QUALITY,
  OUTPUT_TYPE,
  PhotoPrepError,
  browserDeps,
  preparePhoto,
  type Bitmap,
  type PhotoDeps,
  type PhotoProblem,
} from "./photo-prep";

function file(type = "image/jpeg", size = 1000) {
  const blob = new File([new Uint8Array(1)], "photo", { type });
  // The size is what the checks read; a 20 MB array in a test would only waste memory.
  Object.defineProperty(blob, "size", { value: size });
  return blob;
}

interface Options {
  width?: number;
  height?: number;
  decodeFails?: boolean;
  toBlob?: Blob | null;
  drawFails?: boolean;
}

/** Fake pixels and canvas that record what the code asked of them. */
function fake({ width = 1200, height = 800, decodeFails, toBlob, drawFails }: Options = {}) {
  const log = {
    decoded: 0,
    closed: 0,
    surfaceSize: 0,
    steps: [] as string[],
    drawn: null as null | { left: number; top: number; side: number },
    encoded: null as null | { type: string; quality: number },
  };
  const bitmap: Bitmap = {
    width,
    height,
    close: () => {
      log.closed += 1;
    },
  };
  const output = toBlob === undefined ? new Blob(["jpeg-bytes"], { type: OUTPUT_TYPE }) : toBlob;
  const deps: PhotoDeps = {
    decode: async () => {
      log.decoded += 1;
      if (decodeFails) throw new Error("not an image");
      return bitmap;
    },
    surface: (size) => {
      log.surfaceSize = size;
      return {
        fillWhite: () => log.steps.push("fill"),
        drawSquare: (_bitmap, left, top, side) => {
          if (drawFails) throw new Error("canvas lost");
          log.steps.push("draw");
          log.drawn = { left, top, side };
        },
        toBlob: async (type, quality) => {
          log.steps.push("encode");
          log.encoded = { type, quality };
          return output;
        },
      };
    },
  };
  return { deps, log, output };
}

async function problemOf(promise: Promise<unknown>): Promise<PhotoProblem> {
  try {
    await promise;
  } catch (error) {
    expect(error).toBeInstanceOf(PhotoPrepError);
    return (error as PhotoPrepError).problem;
  }
  throw new Error("expected the photo to be refused");
}

describe("preparePhoto: the checks, in order", () => {
  it.each(["image/gif", "image/svg+xml", "image/heic", "application/pdf", ""])(
    "refuses the type %j before decoding anything",
    async (type) => {
      const { deps, log } = fake();
      expect(await problemOf(preparePhoto(file(type), deps))).toBe("type");
      expect(log.decoded).toBe(0);
    },
  );

  it.each(["image/jpeg", "image/png", "image/webp"])("accepts %s", async (type) => {
    const { deps } = fake();
    await expect(preparePhoto(file(type), deps)).resolves.toBeDefined();
  });

  it("refuses a file over 20 MB before decoding, and accepts exactly 20 MB", async () => {
    const { deps, log } = fake();
    expect(await problemOf(preparePhoto(file("image/jpeg", MAX_ORIGINAL_BYTES + 1), deps))).toBe(
      "too_big",
    );
    expect(log.decoded).toBe(0);
    await expect(preparePhoto(file("image/jpeg", MAX_ORIGINAL_BYTES), deps)).resolves.toBeDefined();
  });

  it("checks the type before the size", async () => {
    const { deps } = fake();
    expect(await problemOf(preparePhoto(file("image/gif", MAX_ORIGINAL_BYTES + 1), deps))).toBe(
      "type",
    );
  });

  it("refuses what the browser cannot decode (a HEIC renamed .jpg)", async () => {
    const { deps, log } = fake({ decodeFails: true });
    expect(await problemOf(preparePhoto(file(), deps))).toBe("unreadable");
    expect(log.surfaceSize).toBe(0);
  });

  it.each([
    [127, 500],
    [500, 127],
    [100, 100],
    [1, 1],
  ])("refuses %i x %i: under 128 on a side", async (width, height) => {
    const { deps, log } = fake({ width, height });
    expect(await problemOf(preparePhoto(file(), deps))).toBe("too_small");
    expect(log.surfaceSize).toBe(0);
    expect(log.closed).toBe(1);
  });

  it("accepts exactly 128 x 128", async () => {
    const { deps } = fake({ width: MIN_SIDE, height: MIN_SIDE });
    const prepared = await preparePhoto(file(), deps);
    expect(prepared.side).toBe(128);
  });
});

describe("preparePhoto: the picture", () => {
  it.each([
    // [width, height, left, top, side of the crop, side of the output]
    [1200, 800, 200, 0, 800, 800],
    [600, 1000, 0, 200, 600, 600],
    [4000, 3000, 500, 0, 3000, MAX_OUTPUT_SIDE],
    [3000, 4000, 0, 500, 3000, MAX_OUTPUT_SIDE],
    [2000, 2000, 0, 0, 2000, MAX_OUTPUT_SIDE],
    [1025, 1025, 0, 0, 1025, MAX_OUTPUT_SIDE],
    [1024, 1024, 0, 0, 1024, 1024],
    [301, 200, 50, 0, 200, 200],
  ])(
    "%i x %i: crops the centre square (%i,%i) side %i, output %i px",
    async (width, height, left, top, side, output) => {
      const { deps, log } = fake({ width, height });
      const prepared = await preparePhoto(file(), deps);

      expect(log.drawn).toEqual({ left, top, side });
      expect(log.surfaceSize).toBe(output);
      expect(prepared.side).toBe(output);
    },
  );

  it("paints the white background before the picture, then encodes a JPEG at 0.9", async () => {
    const { deps, log, output } = fake();
    const prepared = await preparePhoto(file("image/png"), deps);

    expect(log.steps).toEqual(["fill", "draw", "encode"]);
    expect(log.encoded).toEqual({ type: "image/jpeg", quality: OUTPUT_QUALITY });
    expect(OUTPUT_QUALITY).toBe(0.9);
    expect(prepared.blob).toBe(output);
  });

  it("uploads the re-encoded blob, never the original file", async () => {
    const original = file();
    const { deps } = fake();
    const prepared = await preparePhoto(original, deps);
    expect(prepared.blob).not.toBe(original);
    expect(prepared.blob.type).toBe("image/jpeg");
  });

  it("closes the decoded picture every time", async () => {
    for (const options of [{}, { width: 50, height: 50 }, { toBlob: null }, { drawFails: true }]) {
      const { deps, log } = fake(options);
      await preparePhoto(file(), deps).catch(() => {});
      expect(log.closed).toBe(1);
    }
  });

  it("an encoder that gives nothing, or a canvas that fails, is unreadable", async () => {
    expect(await problemOf(preparePhoto(file(), fake({ toBlob: null }).deps))).toBe("unreadable");
    expect(await problemOf(preparePhoto(file(), fake({ drawFails: true }).deps))).toBe(
      "unreadable",
    );
  });
});

describe("browserDeps: the real adapter", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function stubBrowser(bitmap: { width: number; height: number; close: () => void }) {
    const context = {
      fillStyle: "",
      imageSmoothingQuality: "",
      fillRect: vi.fn(),
      drawImage: vi.fn(),
    };
    const canvas = {
      width: 0,
      height: 0,
      getContext: vi.fn(() => context),
      toBlob: vi.fn((callback: BlobCallback) => callback(new Blob(["x"], { type: "image/jpeg" }))),
    };
    const createImageBitmap = vi.fn(async () => bitmap);
    vi.stubGlobal("createImageBitmap", createImageBitmap);
    vi.spyOn(document, "createElement").mockReturnValue(canvas as unknown as HTMLElement);
    return { context, canvas, createImageBitmap };
  }

  it("decodes with the EXIF orientation applied and draws the square into the whole canvas", async () => {
    const bitmap = { width: 1600, height: 1200, close: vi.fn() };
    const { context, canvas, createImageBitmap } = stubBrowser(bitmap);
    const input = file("image/jpeg");

    const prepared = await preparePhoto(input, browserDeps());

    expect(createImageBitmap).toHaveBeenCalledWith(input, { imageOrientation: "from-image" });
    expect([canvas.width, canvas.height]).toEqual([1024, 1024]);
    expect(context.fillStyle).toBe("white");
    expect(context.fillRect).toHaveBeenCalledWith(0, 0, 1024, 1024);
    // source: the centre 1200 x 1200 square starting 200 px in; target: all 1024 x 1024.
    expect(context.drawImage).toHaveBeenCalledWith(bitmap, 200, 0, 1200, 1200, 0, 0, 1024, 1024);
    expect(canvas.toBlob).toHaveBeenCalledWith(expect.any(Function), OUTPUT_TYPE, OUTPUT_QUALITY);
    expect(prepared.side).toBe(1024);
    expect(bitmap.close).toHaveBeenCalled();
  });

  it("does not enlarge a small picture", async () => {
    const bitmap = { width: 300, height: 200, close: vi.fn() };
    const { context, canvas } = stubBrowser(bitmap);
    await preparePhoto(file("image/png"), browserDeps());
    expect(canvas.width).toBe(200);
    expect(context.drawImage).toHaveBeenCalledWith(bitmap, 50, 0, 200, 200, 0, 0, 200, 200);
  });

  it("a browser without a 2d canvas context is unreadable, not a crash", async () => {
    const bitmap = { width: 500, height: 500, close: vi.fn() };
    const { canvas } = stubBrowser(bitmap);
    canvas.getContext.mockReturnValue(null as never);
    expect(await problemOf(preparePhoto(file(), browserDeps()))).toBe("unreadable");
    expect(bitmap.close).toHaveBeenCalled();
  });

  it("a picture createImageBitmap rejects is unreadable", async () => {
    stubBrowser({ width: 500, height: 500, close: vi.fn() });
    vi.stubGlobal(
      "createImageBitmap",
      vi.fn(async () => {
        throw new DOMException("The source image could not be decoded.", "InvalidStateError");
      }),
    );
    expect(await problemOf(preparePhoto(file(), browserDeps()))).toBe("unreadable");
  });
});
