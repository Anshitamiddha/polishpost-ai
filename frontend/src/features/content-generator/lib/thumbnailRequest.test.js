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
    assert.equal(buildThumbnailRequest(brief).prompt, brief.prompt);
  });

  it("sends the title and the description next to it", () => {
    const request = buildThumbnailRequest(brief);

    assert.equal(request.title, "AI APP IN 7 DAYS");
    assert.equal(request.description, "I built a full AI app in seven days");
  });

  it("follows the prompt when the user changes it", () => {
    const changed = buildThumbnailRequest({ ...brief, prompt: "soft pastel colors" });

    assert.equal(changed.prompt, "soft pastel colors");
  });

  it("sends an empty prompt as empty, so the backend can leave it out", () => {
    assert.equal(buildThumbnailRequest({ ...brief, prompt: "" }).prompt, "");
  });

  it("sends only what the backend reads", () => {
    assert.deepEqual(Object.keys(buildThumbnailRequest(brief)).sort(), [
      "description",
      "prompt",
      "title",
    ]);
  });
});

describe("thumbnailEndpoint", () => {
  it("puts the workspace in the path", () => {
    assert.equal(thumbnailEndpoint(12), "/api/workspaces/12/thumbnails");
  });
});
