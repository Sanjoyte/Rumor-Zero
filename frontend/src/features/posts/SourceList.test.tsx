import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SourceList } from "./SourceList";

const SOURCES = [
  { value: "10.1038/s41558-024-02102", kind: "doi" as const },
  { value: "https://www.iea.org/reports/renewables-2023", kind: "url" as const },
  { value: "https://xn--bcher-kva.example/%C3%BCber", kind: "url" as const },
];

describe("SourceList", () => {
  it("counts the sources in its heading and numbers them in the order entered", () => {
    render(<SourceList sources={SOURCES} />);
    expect(screen.getByRole("heading", { name: "Sources (3)" })).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items.map((i) => within(i).getByText(/^0\d$/).textContent)).toEqual(["01", "02", "03"]);
    expect(items[0]).toHaveTextContent("10.1038/s41558-024-02102");
    expect(items[1]).toHaveTextContent("https://www.iea.org/reports/renewables-2023");
  });

  it("shows the full value, with the host in punycode as stored", () => {
    render(<SourceList sources={SOURCES} />);
    expect(screen.getByText("https://xn--bcher-kva.example/%C3%BCber")).toBeInTheDocument();
  });

  it("links a DOI to doi.org and a URL to itself, safely, in a new tab", () => {
    render(<SourceList sources={SOURCES} />);
    const doi = screen.getByRole("link", { name: "Open source 01 in a new tab" });
    expect(doi).toHaveAttribute("href", "https://doi.org/10.1038/s41558-024-02102");
    const url = screen.getByRole("link", { name: "Open source 02 in a new tab" });
    expect(url).toHaveAttribute("href", "https://www.iea.org/reports/renewables-2023");
    for (const link of [doi, url]) {
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "nofollow ugc noopener noreferrer");
    }
  });

  it("is the target of '+N more' links", () => {
    const { container } = render(<SourceList sources={SOURCES} />);
    expect(container.querySelector("section#sources")).toBeInTheDocument();
  });

  it("says so when a fact has no sources", () => {
    render(<SourceList sources={[]} />);
    expect(screen.getByRole("heading", { name: "Sources (0)" })).toBeInTheDocument();
    expect(screen.getByText("The author didn't add any sources.")).toBeInTheDocument();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("makes no link out of a value that isn't http(s) or a DOI", () => {
    render(<SourceList sources={[{ value: "javascript:alert(1)", kind: "url" }]} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("javascript:alert(1)")).toBeInTheDocument();
  });
});
