import { useCallback, useEffect, useRef, useState } from "react";

import { MAX_REFERENCE_IMAGES, sortIncomingFiles } from "../lib/referenceImageRules";

// The reference images the user attached, with a preview URL for each.
export function useReferenceImages() {
  const [images, setImages] = useState([]); // [{ id, file, url }]
  const [problems, setProblems] = useState([]);
  const lastId = useRef(0);

  // A preview URL keeps its file in memory until it is revoked. We revoke on
  // remove, and here for whatever is left when the page closes. The ref gives
  // the cleanup the newest list; a plain closure would only see the first one.
  const latestImages = useRef(images);
  useEffect(() => {
    latestImages.current = images;
  }, [images]);
  useEffect(
    () => () => latestImages.current.forEach((image) => URL.revokeObjectURL(image.url)),
    [],
  );

  const addFiles = useCallback(
    (files) => {
      const { accepted, problems: found } = sortIncomingFiles(
        files,
        MAX_REFERENCE_IMAGES - images.length,
      );
      setProblems(found);
      if (accepted.length === 0) return;

      // URLs are created here, in the event handler, not while rendering:
      // creating one is a side effect and rendering must stay free of those.
      const added = accepted.map((file) => {
        lastId.current += 1;
        return { id: `reference-${lastId.current}`, file, url: URL.createObjectURL(file) };
      });
      setImages((current) => [...current, ...added]);
    },
    [images.length],
  );

  const removeImage = useCallback(
    (id) => {
      const target = images.find((image) => image.id === id);
      if (target) URL.revokeObjectURL(target.url);

      setImages((current) => current.filter((image) => image.id !== id));
      setProblems([]);
    },
    [images],
  );

  return {
    images,
    problems,
    addFiles,
    removeImage,
    isFull: images.length >= MAX_REFERENCE_IMAGES,
  };
}
