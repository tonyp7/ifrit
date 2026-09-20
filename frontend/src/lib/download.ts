// Triggers a browser download from an already-fetched Blob: used by the
// Reporting screen's export (see api/timeEntries.ts's exportTimesheetReport):
// fetch + Blob, not a direct <a href>/window.location navigation, so a failed
// request can surface through this app's normal ApiError -> toast.error()
// convention instead of the browser replacing the whole app with a raw error
// response.
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
