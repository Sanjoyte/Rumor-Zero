import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";

function Harness({ onClose = () => {} }: { onClose?: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        New post
      </button>
      <Modal
        open={open}
        onClose={() => {
          onClose();
          setOpen(false);
        }}
        title="Compose a post"
        icon="edit_note"
        footer={<span>3 fact posts left today</span>}
      >
        <textarea aria-label="Post text" />
        <button type="button">Post fact</button>
      </Modal>
    </>
  );
}

const dialog = () => document.querySelector("dialog") as HTMLDialogElement;

describe("Modal", () => {
  it("is closed until opened", () => {
    render(<Harness />);
    expect(dialog()).not.toHaveAttribute("open");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens as a modal dialog named by its title", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "New post" }));
    const modal = screen.getByRole("dialog", { name: "Compose a post" });
    expect(modal).toHaveAttribute("aria-modal", "true");
    expect(modal).toHaveAttribute("open");
  });

  it("moves focus inside when it opens", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "New post" }));
    expect(dialog().contains(document.activeElement)).toBe(true);
  });

  it("focuses the element marked data-autofocus rather than the first control", async () => {
    render(
      <Modal open onClose={() => {}} title="Compose">
        <textarea aria-label="Post text" data-autofocus />
      </Modal>,
    );
    expect(screen.getByLabelText("Post text")).toHaveFocus();
  });

  it("closes on Escape and returns focus to the button that opened it", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const opener = screen.getByRole("button", { name: "New post" });
    await userEvent.click(opener);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
    expect(dialog()).not.toHaveAttribute("open");
    expect(opener).toHaveFocus();
  });

  it("closes from the close button and returns focus", async () => {
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "New post" });
    await userEvent.click(opener);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(dialog()).not.toHaveAttribute("open");
    expect(opener).toHaveFocus();
  });

  it("asks to close when the browser cancels the dialog, and lets the parent decide", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    await userEvent.click(screen.getByRole("button", { name: "New post" }));
    const cancel = new Event("cancel", { cancelable: true });
    fireEvent(dialog(), cancel);
    expect(cancel.defaultPrevented).toBe(true);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows the body, the footer and a blue header icon", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "New post" }));
    expect(screen.getByLabelText("Post text")).toBeInTheDocument();
    expect(screen.getByText("3 fact posts left today")).toBeInTheDocument();
    expect(screen.getByText("edit_note")).toHaveClass("text-secondary");
  });

  it("stays open on a scrim click unless it is allowed to dismiss", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <Modal open onClose={onClose} title="Report post">
        body
      </Modal>,
    );
    fireEvent.click(dialog());
    expect(onClose).not.toHaveBeenCalled();
    rerender(
      <Modal open onClose={onClose} title="Report post" dismissOnBackdrop>
        body
      </Modal>,
    );
    fireEvent.click(dialog());
    expect(onClose).toHaveBeenCalledOnce();
  });
});
