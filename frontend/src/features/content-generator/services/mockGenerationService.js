// PLACEHOLDER generation. Nothing here calls an AI.
//
// The browser cannot call the Python AI service directly (it holds the API
// keys), so it goes through the Spring Boot backend. That route exists for
// thumbnails (see thumbnailService.js) but not yet for captions and hashtags.
// Until then these two functions return simple, template-based results after a
// short pause, so the page can be tried out.
//
// To go live, write a real service with the same function names and swap the
// imports in the hooks. Captions and hashtags already match the AI service's
// response lists; the request will map from `brief`.

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
