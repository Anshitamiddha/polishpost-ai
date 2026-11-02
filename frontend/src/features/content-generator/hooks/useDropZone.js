import { useCallback, useRef, useState } from "react";

// Drag-and-drop for files. Returns whether a file is being dragged over the
// zone, and the four handlers to spread onto the zone's element.
export function useDropZone(onFiles) {
  const [isDragging, setIsDragging] = useState(false);

  // dragenter and dragleave also fire for every child element the pointer
  // crosses. Counting them stops the highlight flickering on and off.
  const depth = useRef(0);

  const onDragEnter = useCallback((event) => {
    if (!event.dataTransfer.types.includes("Files")) return;
    event.preventDefault();
    depth.current += 1;
    setIsDragging(true);
  }, []);

  // Without preventDefault here the browser refuses the drop.
  const onDragOver = useCallback((event) => {
    if (event.dataTransfer.types.includes("Files")) event.preventDefault();
  }, []);

  const onDragLeave = useCallback(() => {
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) setIsDragging(false);
  }, []);

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      depth.current = 0;
      setIsDragging(false);
      onFiles(Array.from(event.dataTransfer.files));
    },
    [onFiles],
  );

  return { isDragging, dropProps: { onDragEnter, onDragOver, onDragLeave, onDrop } };
}
