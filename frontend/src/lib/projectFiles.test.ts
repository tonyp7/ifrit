import { describe, expect, it } from "vitest";

import { availableTags, projectFilesReducer } from "@/lib/projectFiles";
import type { FileTag, ProjectFile } from "@/types/file";

const contract: FileTag = { id: "t-contract", name: "contract" };
const addendum: FileTag = { id: "t-addendum", name: "addendum" };
const invoice: FileTag = { id: "t-invoice", name: "invoice" };

function file(id: string, tags: FileTag[] = []): ProjectFile {
  return {
    file_id: id,
    original_filename: `${id}.pdf`,
    content_type: "application/pdf",
    size_bytes: 10,
    uploaded_at: "2026-10-01T00:00:00Z",
    tags,
  };
}

describe("projectFilesReducer", () => {
  it("replaces the list when loaded", () => {
    expect(projectFilesReducer([file("a")], { type: "loaded", files: [file("b")] })).toEqual([
      file("b"),
    ]);
  });

  it("appends an uploaded file and removes a deleted one", () => {
    const added = projectFilesReducer([file("a")], { type: "added", file: file("b") });
    expect(added.map((f) => f.file_id)).toEqual(["a", "b"]);
    expect(
      projectFilesReducer(added, { type: "removed", fileId: "a" }).map((f) => f.file_id),
    ).toEqual(["b"]);
  });

  it("adds a tag at once, keeping tags ordered by name", () => {
    let files = [file("a", [contract])];
    files = projectFilesReducer(files, { type: "tagAdded", fileId: "a", tag: addendum });
    files = projectFilesReducer(files, { type: "tagAdded", fileId: "a", tag: invoice });
    expect(files[0].tags.map((t) => t.name)).toEqual(["addendum", "contract", "invoice"]);
  });

  it("adding a tag the file already has changes nothing", () => {
    const before = [file("a", [contract])];
    const after = projectFilesReducer(before, {
      type: "tagAdded",
      fileId: "a",
      tag: contract,
    });
    expect(after[0].tags).toHaveLength(1);
  });

  it("only touches the file it names", () => {
    const files = [file("a"), file("b")];
    const after = projectFilesReducer(files, { type: "tagAdded", fileId: "b", tag: contract });
    expect(after[0].tags).toEqual([]);
    expect(after[1].tags).toEqual([contract]);
  });

  it("removes a tag, and removing one the file lacks changes nothing", () => {
    const files = [file("a", [contract, addendum])];
    const after = projectFilesReducer(files, {
      type: "tagRemoved",
      fileId: "a",
      tagId: contract.id,
    });
    expect(after[0].tags).toEqual([addendum]);
    const again = projectFilesReducer(after, {
      type: "tagRemoved",
      fileId: "a",
      tagId: contract.id,
    });
    expect(again[0].tags).toEqual([addendum]);
  });

  it("rolling back one failed tag leaves the others the user changed since", () => {
    let files = [file("a")];
    // Three adds in a row, before any answer comes back.
    for (const tag of [contract, addendum, invoice]) {
      files = projectFilesReducer(files, { type: "tagAdded", fileId: "a", tag });
    }
    // The second one fails: only it is undone.
    files = projectFilesReducer(files, {
      type: "tagRemoved",
      fileId: "a",
      tagId: addendum.id,
    });
    expect(files[0].tags.map((t) => t.name)).toEqual(["contract", "invoice"]);
  });

  it("rolling back a failed removal puts the tag back in order", () => {
    let files = [file("a", [addendum, contract])];
    files = projectFilesReducer(files, {
      type: "tagRemoved",
      fileId: "a",
      tagId: addendum.id,
    });
    files = projectFilesReducer(files, { type: "tagAdded", fileId: "a", tag: addendum });
    expect(files[0].tags.map((t) => t.name)).toEqual(["addendum", "contract"]);
  });

  it("does not mutate the previous state", () => {
    const before = [file("a", [contract])];
    const snapshot = JSON.stringify(before);
    projectFilesReducer(before, { type: "tagAdded", fileId: "a", tag: addendum });
    projectFilesReducer(before, { type: "tagRemoved", fileId: "a", tagId: contract.id });
    expect(JSON.stringify(before)).toBe(snapshot);
  });
});

describe("availableTags", () => {
  const vocabulary = [addendum, contract, invoice];

  it("offers every tag to a file with none", () => {
    expect(availableTags(vocabulary, [])).toEqual(vocabulary);
  });

  it("hides the tags the file already has", () => {
    expect(availableTags(vocabulary, [contract])).toEqual([addendum, invoice]);
  });

  it("offers nothing once the file has them all", () => {
    expect(availableTags(vocabulary, vocabulary)).toEqual([]);
  });
});
