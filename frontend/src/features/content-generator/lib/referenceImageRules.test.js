import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { MAX_REFERENCE_IMAGES, sortIncomingFiles } from "./referenceImageRules.js";

const MB = 1024 * 1024;
const image = (name, type = "image/png", size = 1 * MB) => ({ name, type, size });

describe("sortIncomingFiles", () => {
  it("accepts PNG, JPG and WEBP files", () => {
    const files = [
      image("a.png", "image/png"),
      image("b.jpg", "image/jpeg"),
      image("c.webp", "image/webp"),
    ];

    const { accepted, problems } = sortIncomingFiles(files, MAX_REFERENCE_IMAGES);

    assert.equal(accepted.length, 3);
    assert.deepEqual(problems, []);
  });

  it("rejects other file types and says which file", () => {
    const { accepted, problems } = sortIncomingFiles(
      [image("clip.mp4", "video/mp4"), image("ok.png")],
      MAX_REFERENCE_IMAGES,
    );

    assert.deepEqual(accepted.map((file) => file.name), ["ok.png"]);
    assert.deepEqual(problems, ["clip.mp4 is not a PNG, JPG or WEBP image."]);
  });

  it("accepts a file of exactly 5 MB and rejects one byte more", () => {
    const exactly = image("exact.png", "image/png", 5 * MB);
    const tooBig = image("big.png", "image/png", 5 * MB + 1);

    const { accepted, problems } = sortIncomingFiles([exactly, tooBig], MAX_REFERENCE_IMAGES);

    assert.deepEqual(accepted.map((file) => file.name), ["exact.png"]);
    assert.deepEqual(problems, ["big.png is larger than 5 MB."]);
  });

  it("stops at the number of free slots and reports the rest in one line", () => {
    const files = [image("1.png"), image("2.png"), image("3.png"), image("4.png")];

    const { accepted, problems } = sortIncomingFiles(files, 2);

    assert.deepEqual(accepted.map((file) => file.name), ["1.png", "2.png"]);
    assert.deepEqual(problems, ["You can add up to 5 images, so 2 images were not added."]);
  });

  it("uses the singular when exactly one image does not fit", () => {
    const { problems } = sortIncomingFiles([image("1.png"), image("2.png")], 1);

    assert.deepEqual(problems, ["You can add up to 5 images, so 1 image was not added."]);
  });

  it("adds nothing and reports it when there are no free slots", () => {
    const { accepted, problems } = sortIncomingFiles([image("1.png")], 0);

    assert.equal(accepted.length, 0);
    assert.equal(problems.length, 1);
  });

  it("does not use up a slot on a rejected file", () => {
    const files = [image("bad.gif", "image/gif"), image("good.png")];

    const { accepted } = sortIncomingFiles(files, 1);

    assert.deepEqual(accepted.map((file) => file.name), ["good.png"]);
  });

  it("returns nothing for an empty selection", () => {
    assert.deepEqual(sortIncomingFiles([], 3), { accepted: [], problems: [] });
  });
});
