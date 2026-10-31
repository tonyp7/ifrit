import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  InformationBannerCardView,
  type InformationBannerCardViewProps,
} from "@/components/configuration/InformationBannerCardView";

const baseProps: InformationBannerCardViewProps = {
  loading: false,
  loadFailed: false,
  showOnLogin: false,
  showSiteWide: false,
  draft: { message: "", icon: "info", color: "neutral" },
  dirty: false,
  saving: false,
  onShowOnLoginChange: vi.fn(),
  onShowSiteWideChange: vi.fn(),
  onDraftChange: vi.fn(),
  onSave: vi.fn(),
  onRetry: vi.fn(),
};

function render(overrides: Partial<InformationBannerCardViewProps> = {}) {
  return renderToStaticMarkup(<InformationBannerCardView {...baseProps} {...overrides} />);
}

function saveButtonDisabled(html: string): boolean {
  const tag = /<button[^>]*>(?:(?!<\/button>).)*Save changes<\/button>/s.exec(html)?.[0] ?? "";
  return /\sdisabled=""/.test(tag);
}

// The real disabled attribute, not the `disabled:` Tailwind variants in class names.
function isDisabled(tag: string): boolean {
  return /\sdisabled=""/.test(tag);
}

function textareaTag(html: string): string {
  return /<textarea[^>]*>/.exec(html)?.[0] ?? "";
}

function switchTags(html: string): string[] {
  return [...html.matchAll(/<button[^>]*role="switch"[^>]*>/g)].map(([tag]) => tag);
}

// Names of the chosen option of each single-choice group (icon, then color).
function chosenOptions(html: string): string[] {
  return [
    ...html.matchAll(
      /<button[^>]*role="radio"[^>]*aria-checked="true"[^>]*>(.*?)<\/button>/gs,
    ),
  ].map(([, inner]) => inner.replace(/<[^>]*>/g, ""));
}

function switchStates(html: string): boolean[] {
  return [...html.matchAll(/<button[^>]*role="switch"[^>]*>/g)].map(([tag]) =>
    /aria-checked="true"/.test(tag),
  );
}

describe("InformationBannerCardView", () => {
  it("lists its controls in order", () => {
    const html = render();
    const order = [
      "Information Banner",
      "Display information banner on login page",
      "Display information banner site wide on page top",
      "Message",
      "Visible to everyone, including people who are not signed in.",
      "Icon",
      "Color",
      "Preview",
      "Save changes",
    ].map((text) => html.indexOf(text));

    expect(order.every((at) => at > -1)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it("names every icon and color option in text", () => {
    const html = render();

    for (const name of ["None", "Info", "Warning", "Neutral", "Blue", "Yellow", "Red"]) {
      expect(html).toContain(`${name}</button>`);
    }
  });

  it("shows the defaults: both switches off, empty message, Info, Neutral", () => {
    const html = render();

    expect(switchStates(html)).toEqual([false, false]);
    expect(html).toMatch(/<textarea[^>]*><\/textarea>/);
    expect(chosenOptions(html)).toEqual(["Info", "Neutral"]);
  });

  it("limits the message to 200 characters and counts them", () => {
    const html = render({ draft: { message: "Hello", icon: "info", color: "neutral" } });

    expect(html).toContain('maxLength="200"');
    expect(html).toMatch(/5\s*\/\s*200/);
  });

  it("reflects the saved switch positions", () => {
    expect(switchStates(render({ showOnLogin: true, showSiteWide: false }))).toEqual([
      true,
      false,
    ]);
  });

  it("keeps every control usable whatever the switches and the message say", () => {
    const off = render({ showOnLogin: false, showSiteWide: false });
    const on = render({
      showOnLogin: true,
      showSiteWide: true,
      draft: { message: "Hi", icon: "warning", color: "red" },
    });

    for (const html of [off, on]) {
      expect(isDisabled(textareaTag(html))).toBe(false);
      expect(switchTags(html).some(isDisabled)).toBe(false);
      expect(html).not.toMatch(/<button[^>]*role="radio"[^>]*\sdisabled=""/);
    }
  });

  it("previews the draft in the chosen color, and says nothing is shown while both switches are off", () => {
    const html = render({ draft: { message: "Maintenance", icon: "warning", color: "red" } });

    expect(html).toContain('role="status"');
    expect(html).toContain("Maintenance");
    expect(html).toContain("bg-red-50");
    expect(html).toContain("Not shown anywhere yet.");
  });

  it("drops the not-shown note once a switch is on", () => {
    const html = render({
      showSiteWide: true,
      draft: { message: "Maintenance", icon: "info", color: "blue" },
    });

    expect(html).not.toContain("Not shown anywhere yet.");
  });

  it("says nothing will be shown, instead of an empty block, for an empty or blank draft", () => {
    for (const message of ["", "   \n"]) {
      const html = render({ draft: { message, icon: "info", color: "neutral" } });
      expect(html).toContain("Nothing will be shown.");
      expect(html).not.toContain('role="status"');
    }
  });

  it("offers Save changes only for a differing draft, and says why", () => {
    const clean = render({ dirty: false });
    const dirty = render({ dirty: true });

    expect(saveButtonDisabled(clean)).toBe(true);
    expect(clean).not.toContain("You have unsaved changes.");
    expect(saveButtonDisabled(dirty)).toBe(false);
    expect(dirty).toContain("You have unsaved changes.");
  });

  it("locks the controls and Save while saving", () => {
    const html = render({ dirty: true, saving: true });

    expect(saveButtonDisabled(html)).toBe(true);
    expect(isDisabled(textareaTag(html))).toBe(true);
    expect(switchTags(html).every(isDisabled)).toBe(true);
  });

  it("disables everything while loading and shows no 'not shown' note", () => {
    const html = render({
      loading: true,
      showOnLogin: null,
      showSiteWide: null,
      draft: null,
    });

    expect(isDisabled(textareaTag(html))).toBe(true);
    expect(switchTags(html).every(isDisabled)).toBe(true);
    expect(saveButtonDisabled(html)).toBe(true);
    expect(html).not.toContain("Not shown anywhere yet.");
  });

  it("offers a retry after a failed load", () => {
    const html = render({
      loadFailed: true,
      showOnLogin: null,
      showSiteWide: null,
      draft: null,
    });

    expect(html).toContain("Couldn&#x27;t load the information banner settings.");
    expect(html).toContain("Try again");
  });

  it("makes the choices at least 44 px tall and lets them wrap", () => {
    const html = render();

    expect(html).toContain("min-h-11");
    expect(html).toContain("flex-wrap");
  });
});
