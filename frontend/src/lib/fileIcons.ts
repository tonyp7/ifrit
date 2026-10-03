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
  type LucideIcon,
} from "lucide-react";

export interface FileIconSpec {
  Icon: LucideIcon;
  /** Light and dark color classes, written out in full so Tailwind sees them. */
  className: string;
}

const PDF: FileIconSpec = { Icon: FileText, className: "text-red-500 dark:text-red-400" };
const DOCUMENT: FileIconSpec = {
  Icon: FileText,
  className: "text-blue-500 dark:text-blue-400",
};
const PLAIN_TEXT: FileIconSpec = { Icon: FileText, className: "text-muted-foreground" };
const SPREADSHEET: FileIconSpec = {
  Icon: FileSpreadsheet,
  className: "text-green-600 dark:text-green-400",
};
const PRESENTATION: FileIconSpec = {
  Icon: MonitorPlay,
  className: "text-orange-500 dark:text-orange-400",
};
const IMAGE: FileIconSpec = {
  Icon: FileImage,
  className: "text-purple-500 dark:text-purple-400",
};
// This lucide-react version names these icons FileVideo and FileAudio; newer releases
// renamed them file-play and file-headphone, with the same drawings.
const VIDEO: FileIconSpec = { Icon: FileVideo, className: "text-pink-500 dark:text-pink-400" };
const AUDIO: FileIconSpec = { Icon: FileAudio, className: "text-pink-500 dark:text-pink-400" };
const ARCHIVE: FileIconSpec = {
  Icon: FileArchive,
  className: "text-yellow-600 dark:text-yellow-400",
};
const CODE: FileIconSpec = { Icon: FileCode, className: "text-slate-500 dark:text-slate-400" };
const EMAIL: FileIconSpec = { Icon: Mail, className: "text-sky-500 dark:text-sky-400" };
const CERTIFICATE: FileIconSpec = {
  Icon: FileKey,
  className: "text-amber-600 dark:text-amber-400",
};
const UNKNOWN: FileIconSpec = { Icon: File, className: "text-muted-foreground" };

const BY_EXTENSION: Record<string, FileIconSpec> = {
  pdf: PDF,
  doc: DOCUMENT,
  docx: DOCUMENT,
  rtf: DOCUMENT,
  odt: DOCUMENT,
  txt: PLAIN_TEXT,
  md: PLAIN_TEXT,
  xls: SPREADSHEET,
  xlsx: SPREADSHEET,
  csv: SPREADSHEET,
  ods: SPREADSHEET,
  ppt: PRESENTATION,
  pptx: PRESENTATION,
  key: PRESENTATION,
  png: IMAGE,
  jpg: IMAGE,
  jpeg: IMAGE,
  gif: IMAGE,
  webp: IMAGE,
  svg: IMAGE,
  heic: IMAGE,
  mp4: VIDEO,
  mov: VIDEO,
  webm: VIDEO,
  mp3: AUDIO,
  wav: AUDIO,
  m4a: AUDIO,
  zip: ARCHIVE,
  rar: ARCHIVE,
  "7z": ARCHIVE,
  gz: ARCHIVE,
  json: CODE,
  xml: CODE,
  html: CODE,
  eml: EMAIL,
  msg: EMAIL,
  p12: CERTIFICATE,
  pem: CERTIFICATE,
  cer: CERTIFICATE,
};

/** Every extension the table knows. It is also the set the server accepts for project
 * documents, so the file chooser can offer exactly these. */
export const KNOWN_FILE_EXTENSIONS = Object.keys(BY_EXTENSION);

function fromContentType(contentType: string | null | undefined): FileIconSpec | null {
  if (!contentType) return null;
  const type = contentType.toLowerCase();
  if (type === "application/pdf") return PDF;
  if (type.startsWith("image/")) return IMAGE;
  if (type.startsWith("video/")) return VIDEO;
  if (type.startsWith("audio/")) return AUDIO;
  return null;
}

/** The text after the last dot, lowercased: `contract.final.v2.pdf` is `pdf`. */
function extensionOf(filename: string): string | null {
  const dot = filename.lastIndexOf(".");
  if (dot === -1 || dot === filename.length - 1) return null;
  return filename.slice(dot + 1).toLowerCase();
}

/**
 * The icon and colour of a file. The content type decides when it names a category (PDF,
 * image, video, audio); otherwise the last extension segment of the name does, and
 * anything unrecognized gets the generic file icon.
 */
export function resolveFileIcon({
  contentType,
  filename,
}: {
  contentType?: string | null;
  filename: string;
}): FileIconSpec {
  const byType = fromContentType(contentType);
  if (byType) return byType;
  const extension = extensionOf(filename);
  return (extension && BY_EXTENSION[extension]) || UNKNOWN;
}
