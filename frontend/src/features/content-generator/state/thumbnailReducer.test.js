import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  getActiveVersion,
  initialThumbnailState,
  thumbnailReducer,
} from "./thumbnailReducer.js";

const concepts = [
  { headline: "One", palette: 0 },
  { headline: "Two", palette: 1 },
  { headline: "Three", palette: 2 },
];

function generated() {
  return thumbnailReducer(initialThumbnailState, { type: "generation_succeeded", concepts });
}

function revisionOf(state, id, overrides = {}) {
  const variation = state.variations.find((candidate) => candidate.id === id);
  return {
    type: "revision_succeeded",
    id,
    parentVersionId: variation.activeVersionId,
    kind: "edit",
    prompt: "make it brighter",
    art: { headline: "One", palette: 3 },
    ...overrides,
  };
}

describe("thumbnailReducer", () => {
  it("turns each concept into a variation with an original v1", () => {
    const state = generated();

    assert.equal(state.variations.length, 3);
    for (const variation of state.variations) {
      assert.equal(variation.versions.length, 1);
      assert.equal(variation.versions[0].number, 1);
      assert.equal(variation.versions[0].parentId, null);
      assert.equal(variation.versions[0].kind, "original");
      assert.equal(variation.activeVersionId, variation.versions[0].id);
    }
  });

  it("shows the generating flag between start and finish", () => {
    const started = thumbnailReducer(initialThumbnailState, { type: "generation_started" });
    assert.equal(started.generating, true);

    const finished = thumbnailReducer(started, { type: "generation_succeeded", concepts });
    assert.equal(finished.generating, false);
  });

  it("records a failed generation and clears the flag", () => {
    const started = thumbnailReducer(initialThumbnailState, { type: "generation_started" });
    const failed = thumbnailReducer(started, { type: "generation_failed", message: "No luck" });

    assert.equal(failed.generating, false);
    assert.equal(failed.error, "No luck");
  });

  it("adds a new version that points back at its parent and makes it active", () => {
    const first = generated();
    const id = first.variations[0].id;

    const next = thumbnailReducer(first, revisionOf(first, id));
    const variation = next.variations[0];

    assert.equal(variation.versions.length, 2);
    assert.equal(variation.versions[1].number, 2);
    assert.equal(variation.versions[1].parentId, variation.versions[0].id);
    assert.equal(variation.versions[1].prompt, "make it brighter");
    assert.equal(getActiveVersion(variation).id, variation.versions[1].id);
    assert.equal(variation.busy, false);
  });

  it("keeps every earlier version when more are added", () => {
    let state = generated();
    const id = state.variations[0].id;

    state = thumbnailReducer(state, revisionOf(state, id));
    state = thumbnailReducer(state, revisionOf(state, id, { kind: "regenerate", prompt: "" }));
    const variation = state.variations[0];

    assert.deepEqual(
      variation.versions.map((version) => version.number),
      [1, 2, 3],
    );
    // v3 was made from v2, which was made from v1: the history forms a chain.
    assert.equal(variation.versions[2].parentId, variation.versions[1].id);
    assert.equal(variation.versions[1].parentId, variation.versions[0].id);
  });

  it("edits only the chosen variation", () => {
    const first = generated();
    const next = thumbnailReducer(first, revisionOf(first, first.variations[1].id));

    assert.equal(next.variations[0].versions.length, 1);
    assert.equal(next.variations[1].versions.length, 2);
    assert.equal(next.variations[2].versions.length, 1);
  });

  it("marks one variation busy, and clears it with an error on failure", () => {
    const first = generated();
    const id = first.variations[0].id;

    const busy = thumbnailReducer(first, { type: "revision_started", id });
    assert.equal(busy.variations[0].busy, true);
    assert.equal(busy.variations[1].busy, false);

    const failed = thumbnailReducer(busy, { type: "revision_failed", id, message: "Nope" });
    assert.equal(failed.variations[0].busy, false);
    assert.equal(failed.variations[0].error, "Nope");
    assert.equal(failed.variations[0].versions.length, 1);
  });

  it("switches the active version, and ignores a version that does not exist", () => {
    let state = generated();
    const id = state.variations[0].id;
    state = thumbnailReducer(state, revisionOf(state, id));
    const [v1, v2] = state.variations[0].versions;

    const back = thumbnailReducer(state, { type: "version_selected", id, versionId: v1.id });
    assert.equal(back.variations[0].activeVersionId, v1.id);

    const ignored = thumbnailReducer(back, { type: "version_selected", id, versionId: "nope" });
    assert.equal(ignored.variations[0].activeVersionId, v1.id);
    assert.notEqual(v2.id, v1.id);
  });

  it("does not let a late answer land on a newer set of variations", () => {
    const firstSet = generated();
    const oldId = firstSet.variations[0].id;
    const lateAnswer = revisionOf(firstSet, oldId);

    const secondSet = thumbnailReducer(firstSet, { type: "generation_succeeded", concepts });
    const after = thumbnailReducer(secondSet, lateAnswer);

    assert.notEqual(secondSet.variations[0].id, oldId);
    assert.equal(after, secondSet);
  });

  it("returns the same state for an unknown action", () => {
    const state = generated();
    assert.equal(thumbnailReducer(state, { type: "something_else" }), state);
  });
});
