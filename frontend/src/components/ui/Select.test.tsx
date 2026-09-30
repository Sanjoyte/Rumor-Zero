import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Select } from "./Select";

describe("Select", () => {
  it("binds the label and changes value", async () => {
    render(
      <Select label="Sort" defaultValue="newest">
        <option value="newest">Newest</option>
        <option value="oldest">Oldest</option>
      </Select>,
    );
    const select = screen.getByLabelText("Sort");
    expect(select).toHaveValue("newest");
    await userEvent.selectOptions(select, "oldest");
    expect(select).toHaveValue("oldest");
  });

  it("uses the Stitch d2 select look with room for the arrow", () => {
    render(
      <Select label="Type">
        <option>All</option>
      </Select>,
    );
    expect(screen.getByLabelText("Type")).toHaveClass(
      "form-select",
      "rounded-lg",
      "pr-10",
      "bg-surface-container-low",
    );
  });

  it("can put the label on the same row", () => {
    render(
      <Select label="Type" inline>
        <option>All</option>
      </Select>,
    );
    expect(screen.getByText("Type")).toHaveClass("font-label-code", "uppercase");
  });
});
