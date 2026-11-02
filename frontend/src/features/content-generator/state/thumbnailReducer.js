// State for the thumbnail variations, as a pure reducer (no React in here).
//
// Every variation keeps ALL of its versions. An edit or a regenerate adds a new
// version that points back at the one it came from (parentId), so nothing is
// ever overwritten and the history can always be shown.

export const initialThumbnailState = {
  // Counts how many sets were generated. It is part of every id, so a late
  // answer for an old set can never land on a variation of a newer set.
  generation: 0,
  generating: false,
  error: null,
  variations: [],
};

function makeVariation(id, concept) {
  const firstVersion = {
    id: `${id}-v1`,
    number: 1,
    parentId: null,
    kind: "original",
    prompt: "",
    art: concept,
  };

  return {
    id,
    busy: false,
    error: null,
    activeVersionId: firstVersion.id,
    versions: [firstVersion],
  };
}

// Applies a change to one variation. An unknown id means that variation is
// gone (a newer set replaced it), so the action is ignored.
function updateVariation(state, id, change) {
  if (!state.variations.some((variation) => variation.id === id)) return state;

  return {
    ...state,
    variations: state.variations.map((variation) =>
      variation.id === id ? change(variation) : variation,
    ),
  };
}

export function thumbnailReducer(state, action) {
  switch (action.type) {
    case "generation_started":
      return { ...state, generating: true, error: null };

    case "generation_succeeded": {
      const generation = state.generation + 1;
      return {
        generation,
        generating: false,
        error: null,
        variations: action.concepts.map((concept, index) =>
          makeVariation(`g${generation}-c${index + 1}`, concept),
        ),
      };
    }

    case "generation_failed":
      return { ...state, generating: false, error: action.message };

    case "revision_started":
      return updateVariation(state, action.id, (variation) => ({
        ...variation,
        busy: true,
        error: null,
      }));

    case "revision_succeeded":
      return updateVariation(state, action.id, (variation) => {
        const number = variation.versions.length + 1;
        const version = {
          id: `${variation.id}-v${number}`,
          number,
          parentId: action.parentVersionId,
          kind: action.kind,
          prompt: action.prompt,
          art: action.art,
        };

        return {
          ...variation,
          busy: false,
          activeVersionId: version.id,
          versions: [...variation.versions, version],
        };
      });

    case "revision_failed":
      return updateVariation(state, action.id, (variation) => ({
        ...variation,
        busy: false,
        error: action.message,
      }));

    case "version_selected":
      return updateVariation(state, action.id, (variation) =>
        variation.versions.some((version) => version.id === action.versionId)
          ? { ...variation, activeVersionId: action.versionId }
          : variation,
      );

    default:
      return state;
  }
}

export function getActiveVersion(variation) {
  return variation.versions.find((version) => version.id === variation.activeVersionId);
}
