import type { FileTag, ProjectFile } from "@/types/file";

export type ProjectFilesAction =
  | { type: "loaded"; files: ProjectFile[] }
  | { type: "added"; file: ProjectFile }
  | { type: "removed"; fileId: string }
  | { type: "tagAdded"; fileId: string; tag: FileTag }
  | { type: "tagRemoved"; fileId: string; tagId: string };

const byName = (a: FileTag, b: FileTag) => a.name.localeCompare(b.name);

/**
 * The project's file list, including the tags on each file. Tag changes are applied here
 * before the server has answered (optimistic updates), so each one is its own action and
 * undoing a failed one is the inverse action for that single tag: a failure never
 * restores a snapshot of the whole list, which would also undo other tags the user has
 * changed since.
 */
export function projectFilesReducer(
  files: ProjectFile[],
  action: ProjectFilesAction,
): ProjectFile[] {
  switch (action.type) {
    case "loaded":
      return action.files;
    case "added":
      return [...files, action.file];
    case "removed":
      return files.filter((file) => file.file_id !== action.fileId);
    case "tagAdded":
      return files.map((file) =>
        file.file_id !== action.fileId || file.tags.some((tag) => tag.id === action.tag.id)
          ? file
          : { ...file, tags: [...file.tags, action.tag].sort(byName) },
      );
    case "tagRemoved":
      return files.map((file) =>
        file.file_id !== action.fileId
          ? file
          : { ...file, tags: file.tags.filter((tag) => tag.id !== action.tagId) },
      );
  }
}

/** The tags still offered for a file: the vocabulary minus what it already carries. */
export function availableTags(vocabulary: FileTag[], fileTags: FileTag[]): FileTag[] {
  const taken = new Set(fileTags.map((tag) => tag.id));
  return vocabulary.filter((tag) => !taken.has(tag.id));
}
