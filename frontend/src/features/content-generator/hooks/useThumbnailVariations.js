import { useCallback, useEffect, useReducer, useRef } from "react";

import { createThumbnailVersion } from "../services/mockGenerationService";
import { generateThumbnail } from "../services/thumbnailService";
import {
  getActiveVersion,
  initialThumbnailState,
  thumbnailReducer,
} from "../state/thumbnailReducer";

function toMessage(error) {
  return error instanceof Error && error.message
    ? error.message
    : "Something went wrong. Please try again.";
}

// Everything the thumbnail section does. Generating asks the backend for one
// real thumbnail. Editing and regenerating a variation are still placeholders.
// The reducer owns the state; this hook does the waiting and tells the reducer
// what happened.
export function useThumbnailVariations() {
  const [state, dispatch] = useReducer(thumbnailReducer, initialThumbnailState);

  // One controller for the whole section. Leaving the page cancels all work.
  const controller = useRef(null);
  useEffect(() => {
    const own = new AbortController();
    controller.current = own;
    return () => own.abort();
  }, []);

  const generate = useCallback(async (brief, workspaceId) => {
    dispatch({ type: "generation_started" });
    try {
      const thumbnail = await generateThumbnail(workspaceId, brief);
      dispatch({ type: "thumbnail_created", thumbnail });
    } catch (error) {
      dispatch({ type: "generation_failed", message: toMessage(error) });
    }
  }, []);

  // Shared by "edit" and "regenerate". It takes the variation from the card, so
  // this callback never changes and the memoised cards do not re-render.
  // Resolves to true if a new version was added.
  const revise = useCallback(async (variation, kind, prompt) => {
    const parent = getActiveVersion(variation);
    dispatch({ type: "revision_started", id: variation.id });

    try {
      const art = await createThumbnailVersion(
        { ...parent.art, kind, prompt },
        { signal: controller.current.signal },
      );
      dispatch({
        type: "revision_succeeded",
        id: variation.id,
        parentVersionId: parent.id,
        kind,
        prompt,
        art,
      });
      return true;
    } catch (error) {
      if (error.name !== "AbortError") {
        dispatch({ type: "revision_failed", id: variation.id, message: toMessage(error) });
      }
      return false;
    }
  }, []);

  const regenerate = useCallback(
    (variation) => revise(variation, "regenerate", ""),
    [revise],
  );
  const edit = useCallback(
    (variation, prompt) => revise(variation, "edit", prompt),
    [revise],
  );
  const selectVersion = useCallback(
    (id, versionId) => dispatch({ type: "version_selected", id, versionId }),
    [],
  );

  return {
    variations: state.variations,
    isGenerating: state.generating,
    error: state.error,
    thumbnail: state.thumbnail,
    generate,
    regenerate,
    edit,
    selectVersion,
  };
}
