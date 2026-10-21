import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Avatar, initialsFor } from "./Avatar";

describe("initialsFor", () => {
  it.each([
    ["Ada Lovelace", "AL"],
    ["ada", "AD"],
    ["  grace   brewster  hopper ", "GB"],
    ["élan vital", "ÉV"],
    ["@visual_user", "VI"],
    ["@", "?"],
    ["", "?"],
    ["   ", "?"],
  ])("%j gives %s", (name, expected) => {
    expect(initialsFor(name)).toBe(expected);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Avatar", () => {
  it("shows initials on the inverse surface when there is no photo", () => {
    render(<Avatar name="Ada Lovelace" />);
    const avatar = screen.getByRole("img", { name: "Ada Lovelace" });
    expect(avatar).toHaveTextContent("AL");
    expect(avatar).toHaveClass("bg-inverse-surface", "text-inverse-on-surface", "rounded-full");
  });

  it("shows the photo when there is one", () => {
    render(<Avatar name="Ada Lovelace" src="/api/v1/avatars/1/2-96.webp" />);
    const photo = screen.getByRole("img", { name: "Ada Lovelace" });
    expect(photo.tagName).toBe("IMG");
    expect(photo).toHaveAttribute("src", "/api/v1/avatars/1/2-96.webp");
    expect(photo).toHaveAttribute("width", "40");
    expect(photo).toHaveAttribute("height", "40");
  });

  it("loads a photo lazily and decodes it off the main thread", () => {
    // One Worker request per photo per browser (ARCHITECTURE 13): off-screen avatars wait.
    render(<Avatar name="Ada Lovelace" src="/api/v1/avatars/1/2-96.webp" />);
    const photo = screen.getByRole("img", { name: "Ada Lovelace" });
    expect(photo).toHaveAttribute("loading", "lazy");
    expect(photo).toHaveAttribute("decoding", "async");
  });

  it("falls back to initials when the photo fails to load", () => {
    render(<Avatar name="Ada Lovelace" src="/broken.webp" />);
    fireEvent.error(screen.getByRole("img", { name: "Ada Lovelace" }));
    const fallback = screen.getByRole("img", { name: "Ada Lovelace" });
    expect(fallback.tagName).toBe("SPAN");
    expect(fallback).toHaveTextContent("AL");
  });

  it("falls back when the photo already failed before React could listen for the error", () => {
    // A server-rendered <img> can 404 before hydration: it is complete but has no width.
    vi.spyOn(HTMLImageElement.prototype, "complete", "get").mockReturnValue(true);
    render(<Avatar name="Ada Lovelace" src="/broken.webp" />);
    const fallback = screen.getByRole("img", { name: "Ada Lovelace" });
    expect(fallback.tagName).toBe("SPAN");
    expect(fallback).toHaveTextContent("AL");
  });

  it("tries again when a different photo arrives after a failure", () => {
    const { rerender } = render(<Avatar name="Ada Lovelace" src="/broken.webp" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByRole("img").tagName).toBe("SPAN");
    rerender(<Avatar name="Ada Lovelace" src="/fixed.webp" />);
    expect(screen.getByRole("img").tagName).toBe("IMG");
  });

  it("treats null and empty src as no photo", () => {
    const { rerender } = render(<Avatar name="Ada Lovelace" src={null} />);
    expect(screen.getByRole("img").tagName).toBe("SPAN");
    rerender(<Avatar name="Ada Lovelace" src="" />);
    expect(screen.getByRole("img").tagName).toBe("SPAN");
  });

  it("is hidden from assistive tech when decorative", () => {
    const { container } = render(<Avatar name="Ada Lovelace" decorative />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
  });

  it("supports the Stitch sizes", () => {
    render(<Avatar name="Ada Lovelace" size={8} />);
    expect(screen.getByRole("img")).toHaveClass("h-8", "w-8");
  });
});
