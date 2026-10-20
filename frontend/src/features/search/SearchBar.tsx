"use client";

import Form from "next/form";
import { useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { MAX_QUERY_LENGTH, type SearchFilter, type SearchType } from "./search-params";

/**
 * Stitch b4's query box: a search glyph, an editable field and a clear "×". It submits a GET to
 * `/search`, so the address stays the page's state. The hidden fields carry the tab and chip
 * only when they aren't the default, which keeps a plain search at `/search?q=…`. Shows `q`
 * again whenever the address brings a new one (the top bar's box, Back).
 */
export function SearchBar({
  q,
  type,
  filter,
}: {
  q: string;
  type: SearchType;
  filter: SearchFilter;
}) {
  const [text, setText] = useState(q);
  const [shownFor, setShownFor] = useState(q);
  const input = useRef<HTMLInputElement>(null);
  // The address changed under us: show it (adjust state while rendering, not in an effect).
  if (q !== shownFor) {
    setShownFor(q);
    setText(q);
  }

  return (
    <Form
      action="/search"
      role="search"
      aria-label="Search results"
      className="relative flex items-center"
    >
      <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-space-md text-on-surface-variant">
        <Icon name="search" size="xl" />
      </span>
      <input
        ref={input}
        name="q"
        type="text"
        aria-label="Search query"
        placeholder="Search posts and people"
        enterKeyHint="search"
        autoComplete="off"
        maxLength={MAX_QUERY_LENGTH}
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="w-full rounded-lg border-0 bg-transparent py-space-sm pr-10 pl-11 font-body-md text-body-md font-medium text-on-surface placeholder:text-outline focus:ring-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-secondary/30"
      />
      {type === "users" && <input type="hidden" name="type" value="users" />}
      {type === "posts" && filter !== "all" && <input type="hidden" name="filter" value={filter} />}
      {text !== "" && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => {
            setText("");
            input.current?.focus();
          }}
          className="absolute inset-y-0 right-0 flex items-center pr-space-md text-outline transition-colors hover:text-on-surface-variant"
        >
          <Icon name="close" size="md" />
        </button>
      )}
    </Form>
  );
}
