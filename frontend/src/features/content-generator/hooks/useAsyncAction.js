import { useCallback, useEffect, useRef, useState } from "react";

function toMessage(error) {
  return error instanceof Error && error.message
    ? error.message
    : "Something went wrong. Please try again.";
}

// Runs one async action (like "generate captions") and tracks its progress:
// idle, loading, success or error. Pass a function that takes
// (input, { signal }), and define it outside the component so it stays stable.
export function useAsyncAction(action) {
  const [state, setState] = useState({ status: "idle", data: null, error: null });

  // If the user clicks twice, only the newest run may update the screen.
  const newestRun = useRef(0);
  const controller = useRef(null);

  // Leaving the page cancels work that is still in flight.
  useEffect(() => () => controller.current?.abort(), []);

  const run = useCallback(
    async (input) => {
      controller.current?.abort();
      const thisController = new AbortController();
      controller.current = thisController;
      const thisRun = ++newestRun.current;

      // Keep the previous result on screen while the next one loads.
      setState((previous) => ({ ...previous, status: "loading", error: null }));

      try {
        const data = await action(input, { signal: thisController.signal });
        if (thisRun === newestRun.current) setState({ status: "success", data, error: null });
      } catch (error) {
        // A cancelled or superseded run is not an error the user should see.
        if (error.name === "AbortError" || thisRun !== newestRun.current) return;
        setState((previous) => ({ ...previous, status: "error", error: toMessage(error) }));
      }
    },
    [action],
  );

  return { ...state, isLoading: state.status === "loading", run };
}
