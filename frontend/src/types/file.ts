/** What the API says about a stored file; its bytes are served by `fileContentUrl`. */
export interface StoredFileInfo {
  file_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}
