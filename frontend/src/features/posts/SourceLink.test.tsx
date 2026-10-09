import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PostSource } from "@/lib/api/types";
import { SourceLink } from "./SourceLink";

const URL_SOURCE: PostSource = {
  value: "https://www.iea.org/reports/renewables-2023",
  kind: "url",
};
const DOI_SOURCE: PostSource = { value: "10.1038/s41558-024-02102", kind: "doi" };

describe("SourceLink", () => {
  it("renders nothing without sources", () => {
    const { container } = render(<SourceLink sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a URL's host, linked to the URL, with the safe link attributes", () => {
    render(<SourceLink sources={[URL_SOURCE]} />);
    const link = screen.getByRole("link", { name: /www\.iea\.org/ });
    expect(link).toHaveAttribute("href", URL_SOURCE.value);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "nofollow ugc noopener noreferrer");
    expect(link).toHaveAttribute("title", URL_SOURCE.value);
    expect(link).toHaveTextContent("(opens in a new tab)");
  });

  it("shows a DOI as doi.org/… and links it to doi.org", () => {
    render(<SourceLink sources={[DOI_SOURCE]} />);
    const link = screen.getByRole("link", { name: /doi\.org\/10\.1038\/s41558-024-02102/ });
    expect(link).toHaveAttribute("href", "https://doi.org/10.1038/s41558-024-02102");
    expect(link).toHaveAttribute("rel", "nofollow ugc noopener noreferrer");
  });

  it("shows only the first source, then how many more there are", () => {
    render(
      <SourceLink
        sources={[DOI_SOURCE, URL_SOURCE, { ...URL_SOURCE, value: "https://b.example/" }]}
      />,
    );
    expect(screen.getByText(/doi\.org\/10\.1038/)).toBeInTheDocument();
    expect(screen.queryByText(/iea\.org/)).toBeNull();
    expect(screen.getByText("+2 more")).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(1); // "+N more" links to the detail page in Part 5
  });

  it("has no '+N more' for a single source", () => {
    render(<SourceLink sources={[URL_SOURCE]} />);
    expect(screen.queryByText(/more/)).toBeNull();
  });

  it("shows the host as stored, in punycode", () => {
    render(<SourceLink sources={[{ value: "https://xn--bcher-kva.example/x", kind: "url" }]} />);
    expect(screen.getByText("xn--bcher-kva.example")).toBeInTheDocument();
  });

  it("never makes a link out of a value that isn't http(s)", () => {
    render(<SourceLink sources={[{ value: "javascript:alert(1)", kind: "url" }]} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("javascript:alert(1)")).toBeInTheDocument();
  });

  it("renders the source as text, never as markup", () => {
    const { container } = render(
      <SourceLink
        sources={[{ value: "https://a.example/<img src=x onerror=alert(1)>", kind: "url" }]}
      />,
    );
    expect(container.querySelector("img")).toBeNull();
  });
});
