// The picture to draw for a thumbnail answer from the backend, or null if
// there is none. It reads only `image.previewDataUrl`, the picture itself as a
// data URL, and never falls back to placeholder art.
//
// The check keeps anything that is not an image data URL out of <img src>.
export function previewSource(thumbnail) {
  const source = thumbnail?.image?.previewDataUrl;

  return typeof source === "string" && source.startsWith("data:image/") ? source : null;
}
