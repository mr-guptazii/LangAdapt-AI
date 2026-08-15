import { describe, expect, it } from "vitest";
import { cn, formatMinutes, formatRelativeTime } from "./utils";

describe("cn", () => {
  it("merges class names and resolves tailwind conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-cream", undefined, "font-bold")).toBe("text-cream font-bold");
  });
});

describe("formatMinutes", () => {
  it("formats sub-hour durations as minutes", () => {
    expect(formatMinutes(45)).toBe("45 min");
  });

  it("formats multi-hour durations as h/m", () => {
    expect(formatMinutes(125)).toBe("2h 5m");
    expect(formatMinutes(120)).toBe("2h");
  });
});

describe("formatRelativeTime", () => {
  it("returns 'today' for the current time", () => {
    expect(formatRelativeTime(new Date().toISOString())).toBe("today");
  });

  it("returns 'X days ago' for a past date within a month", () => {
    const fiveDaysAgo = new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString();
    expect(formatRelativeTime(fiveDaysAgo)).toBe("5 days ago");
  });
});
