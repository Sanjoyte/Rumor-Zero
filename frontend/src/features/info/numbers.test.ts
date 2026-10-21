import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { INFO_NUMBERS as N, SCORE_EVENTS } from "./numbers";

const ARCHITECTURE = fs.readFileSync(
  path.resolve(import.meta.dirname, "../../../../docs/ARCHITECTURE.md"),
  "utf8",
);

/** The default column of the ARCHITECTURE §3 row whose first cell starts with `name`. */
function configDefault(name: string): string {
  const row = ARCHITECTURE.split("\n").find((line) => line.startsWith(`| ${name}`));
  if (!row) throw new Error(`No §3 row starts with "${name}"`);
  return row.split("|")[2].trim();
}

describe("the numbers the help pages quote", () => {
  it.each([
    ["Report threshold", "reportThreshold"],
    ["Report window (hours)", "reportWindowHours"],
    ["Min account age for a report to count (hours)", "reportMinAccountAgeHours"],
    ["Report threshold while an emergency is active", "emergencyReportThreshold"],
    ["Confidence threshold (0–100)", "confidenceThreshold"],
    ["Emergency duration (hours)", "emergencyDurationHours"],
    ["Emergency posts per user per 24 h", "emergencyPostsPerDay"],
    ["Min account age for emergency posts (days)", "emergencyMinAccountAgeDays"],
    ["Min credibility score for emergency posts", "emergencyMinReputation"],
    ["Emergency ban after a FALSE emergency (days)", "emergencyFalseCooldownDays"],
    ["Fact posts per user per **rolling 24 hours**", "factPostsPerDay"],
    ["Sources per fact post", "sourcesPerFact"],
  ] as const)("%s matches ARCHITECTURE §3", (row, key) => {
    expect(configDefault(row)).toBe(String(N[key]));
  });

  it("matches the credibility constants of ARCHITECTURE §3 and §4a", () => {
    expect(configDefault("Credibility: start / prior weight / public after")).toContain(
      `${N.scoreStart} / ${N.scoreImaginaryEvents} imaginary events / ${N.scorePublicAfter} counted events`,
    );
    expect(configDefault("Credibility: reporter credit cap")).toContain(
      `${N.reporterCreditCap} un-reversed \`report_upheld\` credits per rolling ${N.reporterCreditWindowDays} days`,
    );
  });

  it("lists exactly the event kinds of the ARCHITECTURE §4a table", () => {
    const section = ARCHITECTURE.split("## 4a.")[1].split("**One reconciling writer**")[0];
    const documented = [...section.matchAll(/^\| `([a-z_]+)`(?: \/ `([a-z_]+)`)*/gm)].flatMap(
      (match) => match[0].match(/`([a-z_]+)`/g)!.map((kind) => kind.replaceAll("`", "")),
    );
    expect(SCORE_EVENTS.map((event) => event.kind).sort()).toEqual([...documented].sort());
  });
});
