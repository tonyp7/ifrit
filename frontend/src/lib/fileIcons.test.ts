import {
  File,
  FileArchive,
  FileAudio,
  FileCode,
  FileImage,
  FileKey,
  FileSpreadsheet,
  FileText,
  FileVideo,
  Mail,
  MonitorPlay,
} from "lucide-react";
import { describe, expect, it } from "vitest";

import { resolveFileIcon } from "@/lib/fileIcons";

// One row per category of the spec's table: [extensions, icon, light class, dark class].
const TABLE = [
  [["pdf"], FileText, "text-red-500", "dark:text-red-400"],
  [["doc", "docx", "rtf", "odt"], FileText, "text-blue-500", "dark:text-blue-400"],
  [["txt", "md"], FileText, "text-muted-foreground", null],
  [["xls", "xlsx", "csv", "ods"], FileSpreadsheet, "text-green-600", "dark:text-green-400"],
  [["ppt", "pptx", "key"], MonitorPlay, "text-orange-500", "dark:text-orange-400"],
  [
    ["png", "jpg", "jpeg", "gif", "webp", "svg", "heic"],
    FileImage,
    "text-purple-500",
    "dark:text-purple-400",
  ],
  [["mp4", "mov", "webm"], FileVideo, "text-pink-500", "dark:text-pink-400"],
  [["mp3", "wav", "m4a"], FileAudio, "text-pink-500", "dark:text-pink-400"],
  [["zip", "rar", "7z", "gz"], FileArchive, "text-yellow-600", "dark:text-yellow-400"],
  [["json", "xml", "html"], FileCode, "text-slate-500", "dark:text-slate-400"],
  [["eml", "msg"], Mail, "text-sky-500", "dark:text-sky-400"],
  [["p12", "pem", "cer"], FileKey, "text-amber-600", "dark:text-amber-400"],
] as const;

describe("resolveFileIcon by extension", () => {
  for (const [extensions, icon, light, dark] of TABLE) {
    for (const extension of extensions) {
      it(`resolves .${extension} to its category's icon and light and dark colors`, () => {
        const spec = resolveFileIcon({ filename: `file.${extension}` });
        expect(spec.Icon).toBe(icon);
        expect(spec.className.split(" ")).toContain(light);
        if (dark) expect(spec.className.split(" ")).toContain(dark);
      });
    }
  }

  it("ignores the case of the extension", () => {
    expect(resolveFileIcon({ filename: "SCAN.PDF" }).Icon).toBe(FileText);
    expect(resolveFileIcon({ filename: "SCAN.PDF" }).className).toContain("text-red-500");
  });

  it("resolves on the last segment only", () => {
    const spec = resolveFileIcon({ filename: "contract.final.v2.pdf" });
    expect(spec.Icon).toBe(FileText);
    expect(spec.className).toContain("text-red-500");
    // The earlier segments would say otherwise.
    expect(resolveFileIcon({ filename: "report.pdf.zip" }).Icon).toBe(FileArchive);
  });
});

describe("resolveFileIcon fallbacks", () => {
  it("falls back to the generic file for no extension", () => {
    for (const filename of ["README", "trailing."]) {
      const spec = resolveFileIcon({ filename });
      expect(spec.Icon).toBe(File);
      expect(spec.className).toBe("text-muted-foreground");
    }
  });

  it("falls back to the generic file for an unknown extension", () => {
    const spec = resolveFileIcon({ filename: "data.xyz" });
    expect(spec.Icon).toBe(File);
    expect(spec.className).toBe("text-muted-foreground");
  });

  it("treats a dotfile's name as its extension, so an unknown one is generic", () => {
    expect(resolveFileIcon({ filename: ".gitignore" }).Icon).toBe(File);
  });
});

describe("resolveFileIcon by content type", () => {
  it("checks the content type before the extension", () => {
    expect(resolveFileIcon({ contentType: "image/png", filename: "scan" }).Icon).toBe(
      FileImage,
    );
    // A wrong extension does not win over a type that names a category.
    expect(resolveFileIcon({ contentType: "application/pdf", filename: "x.zip" }).Icon).toBe(
      FileText,
    );
    expect(resolveFileIcon({ contentType: "video/mp4", filename: "x.txt" }).Icon).toBe(
      FileVideo,
    );
    expect(resolveFileIcon({ contentType: "audio/mpeg", filename: "x.txt" }).Icon).toBe(
      FileAudio,
    );
  });

  it("falls through to the extension for a type that names no category", () => {
    expect(
      resolveFileIcon({
        contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename: "letter.docx",
      }).className,
    ).toContain("text-blue-500");
    expect(resolveFileIcon({ contentType: "application/zip", filename: "a.xlsx" }).Icon).toBe(
      FileSpreadsheet,
    );
  });

  it("ignores a missing content type", () => {
    expect(resolveFileIcon({ contentType: null, filename: "a.csv" }).Icon).toBe(
      FileSpreadsheet,
    );
    expect(resolveFileIcon({ contentType: undefined, filename: "a.csv" }).Icon).toBe(
      FileSpreadsheet,
    );
  });
});
