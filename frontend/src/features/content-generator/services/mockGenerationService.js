// PLACEHOLDER generation. Nothing here calls an AI.
//
// The browser cannot call the Python AI service directly (it holds the API
// keys), and the Spring Boot route that will forward to it does not exist yet.
// Until then these functions return simple, template-based results after a
// short pause, so the whole page can be built and tried out.
//
// To go live, write a real service with the same function names and swap the
// imports in the hooks. Captions and hashtags already match the AI service's
// response lists; the request will map from `brief`.

// The ".js" is needed so Node's test runner can load this file too.
import { THUMBNAIL_PALETTES } from "../lib/thumbnailPalettes.js";

const FAKE_WORK_MS = 1000;

const GENERIC_HASHTAGS = [
  "#youtube",
  "#contentcreator",
  "#videoideas",
  "#creators",
  "#youtubetips",
];

// Resolves after `ms`, or rejects with an AbortError if the caller cancels.
function wait(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }

    const timer = setTimeout(resolve, ms);
    signal?.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

function shorten(text, maxLength) {
  return text.length <= maxLength ? text : `${text.slice(0, maxLength - 1).trimEnd()}…`;
}

// \p{M} (combining marks, such as Hindi vowel signs) is part of a word. Without
// it, a word like "पायथन" would be cut into pieces at its vowel sign.
function topicWords(topic) {
  return topic.match(/[\p{L}\p{N}\p{M}]+/gu) ?? [];
}

export async function generateCaptions(brief, { signal } = {}) {
  await wait(FAKE_WORK_MS, signal);

  const topic = shorten(brief.topic, 80);
  return [
    `${topic}: the full video is up now. Watch it and tell me what you think.`,
    `Ever wondered about this? ${topic}. The video breaks it down.`,
    `New video: ${topic}. Save it for later and share it with someone who needs it.`,
  ];
}

export async function generateHashtags(brief, { signal } = {}) {
  await wait(FAKE_WORK_MS, signal);

  const fromTopic = topicWords(brief.topic)
    .filter((word) => word.length >= 3)
    .slice(0, 5)
    .map((word) => `#${word.toLowerCase()}`);

  // Repeats are dropped regardless of case, keeping the first one.
  const seen = new Set();
  return [...fromTopic, ...GENERIC_HASHTAGS].filter((tag) => {
    if (seen.has(tag)) return false;
    seen.add(tag);
    return true;
  });
}

// Three headline ideas built from the first words of the topic.
export async function generateThumbnailConcepts(brief, { signal } = {}) {
  await wait(FAKE_WORK_MS, signal);

  const words = topicWords(brief.topic);
  const take = (count) => words.slice(0, count).join(" ");
  const headlines = [take(4), `Watch: ${take(3)}`, `${take(3)} explained`];

  return headlines.map((headline, index) => ({
    headline: headline.trim() || "Your next video",
    palette: index % THUMBNAIL_PALETTES.length,
  }));
}

// A new version of one thumbnail. Same headline, next colours, so a version is
// visibly different from the one it came from.
export async function createThumbnailVersion({ headline, palette, kind }, { signal } = {}) {
  await wait(FAKE_WORK_MS, signal);

  const step = kind === "edit" ? 2 : 1;
  return { headline, palette: (palette + step) % THUMBNAIL_PALETTES.length };
}
