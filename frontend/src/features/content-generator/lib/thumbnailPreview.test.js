import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { previewSource } from "./thumbnailPreview.js";

// The shape the backend answers with after a successful generation.
const answer = {
  status: "complete",
  image: {
    assetId: "a1",
    objectKey: "workspaces/12/generated/a1.png",
    contentType: "image/png",
    previewDataUrl: "data:image/png;base64,AAAA",
  },
};

describe("previewSource", () => {
  it("draws the picture the backend returned", () => {
    assert.equal(previewSource(answer), "data:image/png;base64,AAAA");
  });

  it("draws a different picture when the answer holds a different one", () => {
    const newer = { image: { ...answer.image, previewDataUrl: "data:image/jpeg;base64,BBBB" } };

    assert.equal(previewSource(newer), "data:image/jpeg;base64,BBBB");
  });

  it("has nothing to draw before any generation", () => {
    assert.equal(previewSource(null), null);
    assert.equal(previewSource(undefined), null);
  });

  it("has nothing to draw when the backend sent no preview", () => {
    assert.equal(previewSource({ image: { assetId: "a1" } }), null);
    assert.equal(previewSource({ image: { ...answer.image, previewDataUrl: null } }), null);
  });

  it("does not use the storage key as a picture", () => {
    assert.equal(previewSource({ image: { objectKey: "workspaces/12/generated/a1.png" } }), null);
  });

  it("refuses anything that is not an image data URL", () => {
    for (const bad of ["https://example.com/a.png", "javascript:alert(1)", "data:text/html;base64,AAAA", ""]) {
      assert.equal(previewSource({ image: { previewDataUrl: bad } }), null);
    }
  });
});
