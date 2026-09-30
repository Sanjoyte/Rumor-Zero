import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { TabPanel, Tabs } from "./Tabs";

const TABS = [
  { id: "following", label: "Following" },
  { id: "recent", label: "Recent", count: 12 },
  { id: "saved", label: "Saved" },
];

function Harness({ start = "following" }: { start?: string }) {
  const [value, setValue] = useState(start);
  return (
    <>
      <Tabs tabs={TABS} value={value} onChange={setValue} label="Feed" idPrefix="feed" />
      {TABS.map((tab) => (
        <TabPanel key={tab.id} idPrefix="feed" tab={tab.id} selected={value === tab.id}>
          {tab.label} panel
        </TabPanel>
      ))}
    </>
  );
}

const underline = (name: string | RegExp) =>
  screen.getByRole("tab", { name }).querySelector("span[aria-hidden]");

describe("Tabs", () => {
  it("is a named tablist with the current tab selected", () => {
    render(<Harness />);
    expect(screen.getByRole("tablist", { name: "Feed" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Following" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Recent/ })).toHaveAttribute("aria-selected", "false");
  });

  it("shows the count chip when given one", () => {
    render(<Harness />);
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("roves tabindex: only the selected tab is in the tab order", () => {
    render(<Harness />);
    expect(screen.getByRole("tab", { name: "Following" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: /Recent/ })).toHaveAttribute("tabindex", "-1");
  });

  it("switches on click and shows the matching panel", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("tab", { name: /Recent/ }));
    expect(screen.getByRole("tab", { name: /Recent/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: /Recent/ })).toHaveTextContent("Recent panel");
    expect(screen.queryByText("Following panel")).not.toBeVisible();
  });

  it("moves with the arrow keys, wrapping at both ends, and moves focus", async () => {
    render(<Harness />);
    screen.getByRole("tab", { name: "Following" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /Recent/ })).toHaveFocus();
    expect(screen.getByRole("tab", { name: /Recent/ })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "Saved" })).toHaveFocus();
  });

  it("jumps with Home and End", async () => {
    render(<Harness start="recent" />);
    screen.getByRole("tab", { name: /Recent/ }).focus();
    await userEvent.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Saved" })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Following" })).toHaveAttribute("aria-selected", "true");
  });

  it("draws the underline inside the selected tab only, so it moves", async () => {
    render(<Harness />);
    expect(underline("Following")).not.toBeNull();
    expect(underline(/Recent/)).toBeNull();
    await userEvent.click(screen.getByRole("tab", { name: /Recent/ }));
    expect(underline("Following")).toBeNull();
    expect(underline(/Recent/)).not.toBeNull();
  });
});
