import { useCallback, useReducer } from "react";

import { generateThumbnail } from "../services/thumbnailService";
import { initialThumbnailState, thumbnailReducer } from "../state/thumbnailReducer";

function toMessage(error) {
  return error instanceof Error && error.message
    ? error.message
    : "Something went wrong. Please try again.";
}

// Asks the backend for one real thumbnail. The reducer owns the state; this
// hook does the waiting and tells the reducer what happened.
export function useThumbnailGeneration() {
  const [state, dispatch] = useReducer(thumbnailReducer, initialThumbnailState);

  const generate = useCallback(async (brief, workspaceId) => {
    dispatch({ type: "generation_started" });
    try {
      const thumbnail = await generateThumbnail(workspaceId, brief);
      dispatch({ type: "thumbnail_created", thumbnail });
    } catch (error) {
      dispatch({ type: "generation_failed", message: toMessage(error) });
    }
  }, []);

  return {
    isGenerating: state.generating,
    error: state.error,
    thumbnail: state.thumbnail,
    generate,
  };
}
