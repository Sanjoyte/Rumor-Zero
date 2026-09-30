import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DangerAction, DangerZone } from "./DangerZone";

describe("DangerZone", () => {
  it("is a red-tinted card with a warning title", () => {
    render(
      <DangerZone tag="Irreversible">
        <DangerAction
          title="Delete account"
          description="Removes your profile and posts."
          action={<button type="button">Delete</button>}
        />
      </DangerZone>,
    );
    const zone = screen.getByRole("heading", { name: /Danger zone/ }).closest("section");
    expect(zone).toHaveClass("border-error/30", "bg-error/5", "rounded-lg");
    expect(screen.getByText("Irreversible")).toHaveClass("text-error");
    expect(screen.getByText("Delete account")).toBeInTheDocument();
    expect(screen.getByText("Removes your profile and posts.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });
});
