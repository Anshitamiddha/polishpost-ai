import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { initialThumbnailState, thumbnailReducer } from "./thumbnailReducer.js";

function answer(assetId) {
  return {
    status: "complete",
    image: { assetId, previewDataUrl: `data:image/png;base64,${assetId}` },
  };
}

function run(state, ...actions) {
  return actions.reduce(thumbnailReducer, state);
}

describe("thumbnailReducer", () => {
  it("starts with nothing generated", () => {
    assert.deepEqual(initialThumbnailState, { generating: false, error: null, thumbnail: null });
  });

  it("shows the generating flag between start and finish", () => {
    const started = run(initialThumbnailState, { type: "generation_started" });
    assert.equal(started.generating, true);

    const finished = run(started, { type: "thumbnail_created", thumbnail: answer("a1") });
    assert.equal(finished.generating, false);
  });

  it("keeps the thumbnail the backend returned, exactly as it came", () => {
    const returned = answer("a1");

    const done = run(
      initialThumbnailState,
      { type: "generation_started" },
      { type: "thumbnail_created", thumbnail: returned },
    );

    assert.equal(done.thumbnail, returned);
    assert.equal(done.error, null);
  });

  it("replaces the previous thumbnail with the new one instead of adding to it", () => {
    const second = answer("a2");

    const done = run(
      initialThumbnailState,
      { type: "thumbnail_created", thumbnail: answer("a1") },
      { type: "generation_started" },
      { type: "thumbnail_created", thumbnail: second },
    );

    assert.equal(done.thumbnail, second);
    assert.equal(Array.isArray(done.thumbnail), false);
  });

  it("shows no thumbnail while the next one is being made", () => {
    const state = run(
      initialThumbnailState,
      { type: "thumbnail_created", thumbnail: answer("a1") },
      { type: "generation_started" },
    );

    assert.equal(state.generating, true);
    assert.equal(state.thumbnail, null);
  });

  it("does not keep an old thumbnail after a failed generation, and says why", () => {
    const failed = run(
      initialThumbnailState,
      { type: "thumbnail_created", thumbnail: answer("a1") },
      { type: "generation_started" },
      { type: "generation_failed", message: "No luck" },
    );

    assert.equal(failed.generating, false);
    assert.equal(failed.error, "No luck");
    assert.equal(failed.thumbnail, null);
  });

  it("clears the error when the next generation starts", () => {
    const state = run(
      initialThumbnailState,
      { type: "generation_failed", message: "No luck" },
      { type: "generation_started" },
    );

    assert.equal(state.error, null);
  });

  it("returns the same state for an unknown action", () => {
    const state = run(initialThumbnailState, { type: "thumbnail_created", thumbnail: answer("a1") });

    assert.equal(thumbnailReducer(state, { type: "something_else" }), state);
  });
});
