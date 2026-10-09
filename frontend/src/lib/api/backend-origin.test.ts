import { describe, expect, it } from "vitest";
import { parseBackendOrigin } from "./backend-origin";

describe("parseBackendOrigin", () => {
  it.each([
    ["https://api.example.test", "https://api.example.test"],
    ["https://api.example.test/", "https://api.example.test"],
    ["http://localhost:8000", "http://localhost:8000"],
    ["http://127.0.0.1:8000/", "http://127.0.0.1:8000"],
    ["http://[::1]:8000", "http://[::1]:8000"],
  ])("accepts %s", (value, origin) => {
    expect(parseBackendOrigin(value)).toBe(origin);
  });

  it.each([
    undefined,
    "",
    "not a url",
    "http://api.example.test", // plain http to a real host
    "https://api.example.test/api",
    "https://api.example.test/?x=1",
    "https://api.example.test/#f",
    "https://user:pw@api.example.test",
    "ftp://localhost",
  ])("refuses %s", (value) => {
    expect(parseBackendOrigin(value)).toBeNull();
  });
});
