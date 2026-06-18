import { describe, expect, it } from "vitest";

import { digitizeHref, panelAssetUrl } from "./api";

describe("panelAssetUrl", () => {
  it("routes a staged thumbnail path through the /api proxy", () => {
    expect(panelAssetUrl("/repro-assets/hani/2C.png")).toBe("/api/repro-assets/hani/2C.png");
  });

  it("is empty for an empty/absent thumbnail", () => {
    expect(panelAssetUrl("")).toBe("");
    expect(panelAssetUrl(undefined)).toBe("");
    expect(panelAssetUrl(null)).toBe("");
  });
});

describe("digitizeHref", () => {
  it("builds an /extract link carrying the lift, panel identity, and form", () => {
    const href = digitizeHref("hani", "4C", "/repro-assets/hani/4C.png", "scatter");
    const url = new URL(href, "http://x");
    expect(url.pathname).toBe("/extract");
    expect(url.searchParams.get("img")).toBe("/repro-assets/hani/4C.png");
    expect(url.searchParams.get("panel")).toBe("hani:4C");
    expect(url.searchParams.get("form")).toBe("scatter");
  });
});
