import { useCallback, useEffect, useRef, useState } from "react";

// Copies text and remembers which item was copied for a moment, so its button
// can say "Copied". `key` tells the buttons apart.
export function useCopyToClipboard(resetAfterMs = 1800) {
  const [copiedKey, setCopiedKey] = useState(null);
  const timer = useRef(null);

  // Do not fire the timer after the page is gone.
  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = useCallback(
    async (text, key) => {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        // Blocked, or not available on this connection. The button stays "Copy".
        return;
      }

      setCopiedKey(key);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopiedKey(null), resetAfterMs);
    },
    [resetAfterMs],
  );

  return { copiedKey, copy };
}
