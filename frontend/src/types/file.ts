/** What the API says about a stored file; its bytes are served by `fileContentUrl`. */
export interface StoredFileInfo {
  file_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}

/** One entry of the fixed tag vocabulary a project file can carry. */
export interface FileTag {
  id: string;
  name: string;
}

/** A file attached to a project, with the tags on it. */
export interface ProjectFile extends StoredFileInfo {
  tags: FileTag[];
}
