import { useCallback, useState } from "react";

// A controlled text field with a character limit and counter.
// Only the text is stored. Length, remaining characters and "is it blank" are
// worked out on every render, so they can never drift out of sync with it.
export function useLimitedText(maxLength, initialValue = "") {
  const [value, setValue] = useState(initialValue.slice(0, maxLength));

  // Pasting can bypass the input's maxLength, so we cut the text ourselves too.
  const onChange = useCallback(
    (event) => setValue(event.target.value.slice(0, maxLength)),
    [maxLength],
  );

  return {
    value,
    onChange,
    maxLength,
    length: value.length,
    isBlank: value.trim() === "",
  };
}
