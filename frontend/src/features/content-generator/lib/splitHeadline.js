// Breaks a headline into short uppercase lines that fit on a thumbnail.
// SVG text does not wrap by itself, so we do the wrapping here.
export function splitHeadline(text, maxLineChars = 12, maxLines = 3) {
  const words = text.toUpperCase().split(/\s+/).filter(Boolean);
  const lines = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;

    // A single long word still gets its own line; we shorten it below.
    if (!current || candidate.length <= maxLineChars) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
  }
  if (current) lines.push(current);

  return lines
    .slice(0, maxLines)
    .map((line) => (line.length > maxLineChars ? `${line.slice(0, maxLineChars - 1)}…` : line));
}
