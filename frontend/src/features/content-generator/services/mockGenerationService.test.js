import assert from "node:assert/strict";
import { afterEach, describe, it, mock } from "node:test";

import {
  createThumbnailVersion,
  generateCaptions,
  generateHashtags,
  generateThumbnailConcepts,
} from "./mockGenerationService.js";

// The service pauses for a second to imitate real work. Fake timers let a test
// skip that pause instead of waiting for it.
async function finished(start) {
  mock.timers.enable({ apis: ["setTimeout"] });
  const pending = start(); // the timer is registered before this returns
  mock.timers.tick(1000);
  return pending;
}

afterEach(() => mock.timers.reset());

describe("mockGenerationService", () => {
  it("returns three captions that mention the topic", async () => {
    const captions = await finished(() => generateCaptions({ topic: "Sunrise hike" }));

    assert.equal(captions.length, 3);
    assert.ok(captions.every((caption) => caption.includes("Sunrise hike")));
  });

  it("shortens a very long topic inside captions", async () => {
    const topic = "word ".repeat(100).trim();
    const captions = await finished(() => generateCaptions({ topic }));

    assert.ok(captions.every((caption) => caption.length < 200));
  });

  it("builds hashtags from the topic and adds general ones, without repeats", async () => {
    const hashtags = await finished(() =>
      generateHashtags({ topic: "YouTube tips for YouTube" }),
    );

    assert.ok(hashtags.includes("#tips"));
    // "youtube" is in the topic twice and in the general list once.
    assert.equal(hashtags.filter((tag) => tag === "#youtube").length, 1);
    assert.ok(hashtags.every((tag) => /^#[\p{L}\p{N}\p{M}]+$/u.test(tag)));
  });

  it("keeps hashtags in other scripts", async () => {
    const hashtags = await finished(() => generateHashtags({ topic: "पायथन सीखें" }));

    assert.ok(hashtags.includes("#पायथन"));
  });

  it("makes three thumbnail concepts with a headline and a palette", async () => {
    const concepts = await finished(() =>
      generateThumbnailConcepts({ topic: "Build AI apps faster today" }),
    );

    assert.equal(concepts.length, 3);
    for (const concept of concepts) {
      assert.ok(concept.headline.length > 0);
      assert.equal(typeof concept.palette, "number");
    }
  });

  it("still makes concepts when the topic has no usable words", async () => {
    const concepts = await finished(() => generateThumbnailConcepts({ topic: "!!!" }));

    assert.ok(concepts.every((concept) => concept.headline.length > 0));
  });

  it("makes a new version in a different palette, keeping the headline", async () => {
    const art = await finished(() =>
      createThumbnailVersion({ headline: "Hello", palette: 0, kind: "edit" }),
    );

    assert.equal(art.headline, "Hello");
    assert.notEqual(art.palette, 0);
  });

  it("stops waiting when cancelled", async () => {
    const controller = new AbortController();
    const pending = generateCaptions({ topic: "Anything" }, { signal: controller.signal });
    controller.abort();

    await assert.rejects(pending, { name: "AbortError" });
  });

  it("refuses to start when the signal is already cancelled", async () => {
    const controller = new AbortController();
    controller.abort();

    await assert.rejects(
      generateHashtags({ topic: "Anything" }, { signal: controller.signal }),
      { name: "AbortError" },
    );
  });
});
