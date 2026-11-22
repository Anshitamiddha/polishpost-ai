import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { buildThumbnailRequest, thumbnailEndpoint } from "./thumbnailRequest.js";

const brief = {
  topic: "AI APP IN 7 DAYS",
  description: "I built a full AI app in seven days",
  prompt: "Create a bold, cinematic YouTube thumbnail. Leave space for a short headline.",
  referenceCount: 2,
};

describe("buildThumbnailRequest", () => {
  it("sends the global creative prompt exactly as it is in the brief", () => {
    assert.equal(buildThumbnailRequest(brief).global_prompt, brief.prompt);
  });

  it("sends the video topic and the description next to it", () => {
    const request = buildThumbnailRequest(brief);

    assert.equal(request.video_topic, "AI APP IN 7 DAYS");
    assert.equal(request.description, "I built a full AI app in seven days");
  });

  it("follows the prompt when the user changes it", () => {
    const changed = buildThumbnailRequest({ ...brief, prompt: "soft pastel colors" });

    assert.equal(changed.global_prompt, "soft pastel colors");
  });

  it("sends an empty prompt as empty, so the backend can leave it out", () => {
    assert.equal(buildThumbnailRequest({ ...brief, prompt: "" }).global_prompt, "");
  });

  it("does not send the old field names", () => {
    const request = buildThumbnailRequest(brief);

    for (const old of ["title", "prompt", "heading", "subtitle", "visual_style", "workspace_id"]) {
      assert.equal(old in request, false);
    }
  });

  it("never asks for a number of thumbnails, so the backend always makes exactly one", () => {
    const request = buildThumbnailRequest({ ...brief, count: 3, variations: 3, imageCount: 3 });

    for (const key of ["count", "variations", "imageCount", "image_count", "numImages"]) {
      assert.equal(key in request, false);
    }
  });

  it("sends only what the backend reads", () => {
    assert.deepEqual(Object.keys(buildThumbnailRequest(brief)).sort(), [
      "description",
      "global_prompt",
      "video_topic",
    ]);
  });
});

describe("thumbnailEndpoint", () => {
  it("puts the workspace in the path", () => {
    assert.equal(thumbnailEndpoint(12), "/api/workspaces/12/thumbnails");
  });
});
