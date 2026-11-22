// State for the thumbnail section, as a pure reducer (no React in here).
//
// There is at most one thumbnail: the one the backend returned for the latest
// generation. Starting a new generation, or failing one, clears it, so an old
// picture is never shown as if it were the newest.

export const initialThumbnailState = {
  generating: false,
  error: null,
  thumbnail: null,
};

export function thumbnailReducer(state, action) {
  switch (action.type) {
    case "generation_started":
      return { generating: true, error: null, thumbnail: null };

    case "thumbnail_created":
      return { generating: false, error: null, thumbnail: action.thumbnail };

    case "generation_failed":
      return { generating: false, error: action.message, thumbnail: null };

    default:
      return state;
  }
}
