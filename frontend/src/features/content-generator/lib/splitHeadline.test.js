import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { splitHeadline } from "./splitHeadline.js";

describe("splitHeadline", () => {
  it("uppercases the text", () => {
    assert.deepEqual(splitHeadline("build ai"), ["BUILD AI"]);
  });

  it("wraps words onto new lines at the line limit", () => {
    assert.deepEqual(splitHeadline("build ai apps faster"), ["BUILD AI", "APPS FASTER"]);
  });

  it("keeps at most the allowed number of lines", () => {
    const lines = splitHeadline("one two three four five six seven eight", 5, 3);
    assert.equal(lines.length, 3);
  });

  it("shortens a single word that is longer than a line", () => {
    assert.deepEqual(splitHeadline("extraordinarily", 8), ["EXTRAOR…"]);
  });

  it("ignores extra spaces", () => {
    assert.deepEqual(splitHeadline("  a    b  "), ["A B"]);
  });

  it("returns no lines for empty text", () => {
    assert.deepEqual(splitHeadline("   "), []);
  });
});
