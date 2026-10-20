import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Highlight } from "./Highlight";

const marks = (container: HTMLElement) =>
  [...container.querySelectorAll("mark")].map((mark) => mark.textContent);

describe("Highlight", () => {
  it("wraps the matching words in mark and leaves the rest as text", () => {
    const { container } = render(
      <Highlight text="Storm warning for the coast" terms={["storm"]} />,
    );
    expect(marks(container)).toEqual(["Storm"]);
    expect(container.textContent).toBe("Storm warning for the coast");
  });

  it("renders plain text when there are no terms", () => {
    const { container } = render(<Highlight text="Nothing to mark" terms={[]} />);
    expect(container.querySelector("mark")).toBeNull();
    expect(container.textContent).toBe("Nothing to mark");
  });

  it("uses Stitch's highlight tokens and stays upright", () => {
    const { container } = render(<Highlight text="storm" terms={["storm"]} />);
    const mark = container.querySelector("mark");
    expect(mark).toHaveClass("bg-secondary-fixed", "text-on-secondary-fixed", "not-italic");
  });

  it("never turns text into elements", () => {
    const text = '<script>alert(1)</script> <b>storm</b> & "quotes"';
    const { container } = render(<Highlight text={text} terms={["storm", "script"]} />);
    expect(container.querySelector("script, b")).toBeNull();
    expect(container.textContent).toBe(text);
    expect(marks(container)).toEqual(["script", "script", "storm"]);
  });
});
