import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider, initReactI18next } from "react-i18next";
import { describe, expect, it, vi } from "vitest";

import common from "../../../public/locales/en/common.json";
import projects from "../../../public/locales/en/projects.json";
import {
  SupportingDocumentsSectionView,
  type SupportingDocumentsSectionViewProps,
} from "@/components/projects/SupportingDocumentsSectionView";
import type { FileTag, ProjectFile } from "@/types/file";

const contract: FileTag = { id: "t1", name: "contract" };
const addendum: FileTag = { id: "t2", name: "addendum" };
const vocabulary = [addendum, contract];

function file(id: string, name: string, tags: FileTag[] = [], size = 2_100_000): ProjectFile {
  return {
    file_id: id,
    original_filename: name,
    content_type: "application/pdf",
    size_bytes: size,
    uploaded_at: "2026-10-01T00:00:00Z",
    tags,
  };
}

const idle = { status: "idle", progress: 0, error: null, fileName: null } as const;

const baseProps: SupportingDocumentsSectionViewProps = {
  files: [],
  vocabulary,
  loadFailed: false,
  readOnly: false,
  upload: idle,
  deleteTarget: null,
  onBrowse: vi.fn(),
  onDownload: vi.fn(),
  onAddTag: vi.fn(),
  onRemoveTag: vi.fn(),
  onDeleteRequest: vi.fn(),
  onDeleteCancel: vi.fn(),
  onDeleteConfirm: vi.fn(),
};

// Real translations; a key the section uses that is missing from the locale files is
// recorded so the test fails on it.
function render(overrides: Partial<SupportingDocumentsSectionViewProps> = {}) {
  const missing: string[] = [];
  const i18n = createInstance();
  void i18n.use(initReactI18next).init({
    lng: "en",
    resources: { en: { common, projects } },
    defaultNS: "common",
    initAsync: false,
    saveMissing: true,
    missingKeyHandler: (_lngs, ns, key) => missing.push(`${ns}:${key}`),
    interpolation: { escapeValue: false },
  });
  const html = renderToStaticMarkup(
    <I18nextProvider i18n={i18n}>
      <SupportingDocumentsSectionView {...baseProps} {...overrides} />
    </I18nextProvider>,
  );
  expect(missing).toEqual([]);
  return html;
}

/** The opening tag of the button with this accessible name. */
function buttonNamed(html: string, label: string): string {
  const match = html.match(new RegExp(`<button[^>]*aria-label="${label}"[^>]*>`));
  if (!match) throw new Error(`No button named ${label}`);
  return match[0];
}

describe("SupportingDocumentsSectionView", () => {
  it("shows the title and the upload button directly, with no rows, for a project without files", () => {
    const html = render();
    expect(html).toContain("Supporting Documents");
    expect(html).toContain("Upload File...");
    expect(html).not.toContain("<li ");
    expect(html).not.toContain("<ul");
    expect(html.indexOf("Supporting Documents")).toBeLessThan(html.indexOf("Upload File..."));
  });

  it("lists the files in order, each with a trash button, name, size and tags", () => {
    const html = render({
      files: [
        file("a", "contract.pdf", [contract]),
        file("b", "signed-add-2027.pdf", [addendum, contract], 1_400_000),
      ],
    });
    expect(html.match(/<li /g)).toHaveLength(2);
    expect(html.indexOf("contract.pdf")).toBeLessThan(html.indexOf("signed-add-2027.pdf"));
    expect(html).toContain("2.1 MB");
    expect(html).toContain("1.4 MB");
    expect(html).toContain('aria-label="Delete file contract.pdf"');
    expect(html).toContain('aria-label="Delete file signed-add-2027.pdf"');
  });

  it("puts the upload button below the list", () => {
    const html = render({ files: [file("a", "contract.pdf")] });
    expect(html.indexOf("contract.pdf")).toBeLessThan(html.indexOf("Upload File..."));
  });

  it("renders each tag as a badge holding a named remove button, then a + Tag button", () => {
    const html = render({ files: [file("b", "signed.pdf", [addendum, contract])] });
    expect(html).toContain('aria-label="Remove tag addendum"');
    expect(html).toContain('aria-label="Remove tag contract"');
    expect(html).toContain('aria-label="Add tag"');
    // The + Tag button follows the last badge.
    expect(html.lastIndexOf('aria-label="Remove tag contract"')).toBeLessThan(
      html.indexOf('aria-label="Add tag"'),
    );
    // Remove buttons are real buttons, so Tab reaches them.
    expect(html).toMatch(/<button[^>]*aria-label="Remove tag contract"/);
  });

  it("lets the tags wrap below the name on narrow screens", () => {
    const html = render({ files: [file("a", "contract.pdf", [contract])] });
    // The name group takes the whole line below the sm breakpoint, which wraps the tags
    // beneath it; from sm up both share one line.
    expect(html).toMatch(/flex flex-wrap items-center[^"]*"/);
    expect(html).toContain("w-full min-w-0");
    expect(html).toContain("sm:w-auto");
  });

  it("shows the file-type icon in its category color, with dark variant", () => {
    const html = render({ files: [file("a", "contract.pdf")] });
    expect(html).toContain("text-red-500");
    expect(html).toContain("dark:text-red-400");
  });

  it("lets the chooser offer only the accepted extensions", () => {
    const html = render();
    expect(html).toMatch(/accept="[^"]*\.pdf[^"]*"/);
    expect(html).not.toMatch(/accept="[^"]*\.exe/);
  });

  it("disables upload, delete and tag controls on a closed project but keeps downloads live", () => {
    const html = render({ readOnly: true, files: [file("a", "contract.pdf", [contract])] });
    expect(buttonNamed(html, "Delete file contract.pdf")).toContain('disabled=""');
    expect(buttonNamed(html, "Remove tag contract")).toContain('disabled=""');
    expect(buttonNamed(html, "Add tag")).toContain('disabled=""');
    // The upload button has no label of its own: it is the one carrying the upload icon.
    expect(html).toMatch(
      /<button[^>]*disabled=""[^>]*><svg[^>]*lucide-upload[\s\S]*?Upload File\.\.\./,
    );
    // The name button is the download: it stays enabled.
    const download = html.match(/<button[^>]*>(?=<span class="truncate">contract\.pdf)/);
    expect(download?.[0]).not.toContain(`disabled=""`);
  });

  it("is not read-only for an open project", () => {
    const html = render({ files: [file("a", "contract.pdf", [contract])] });
    expect(html).not.toContain('disabled=""');
  });

  it("shows progress and disables the upload button while uploading", () => {
    const html = render({
      upload: { status: "uploading", progress: 40, error: null, fileName: "big.pdf" },
    });
    expect(html).toContain("Uploading big.pdf…");
    expect(html).toContain('role="progressbar"');
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*><svg[^>]*lucide-upload/);
  });

  it("shows the server's reason when an upload is refused", () => {
    const html = render({
      upload: {
        status: "rejected",
        progress: 0,
        error: "This file type is not allowed",
        fileName: null,
      },
    });
    expect(html).toContain('role="alert"');
    expect(html).toContain("This file type is not allowed");
  });

  it("says so when the documents could not be loaded", () => {
    expect(render({ loadFailed: true })).toContain("Failed to load documents.");
  });
});
