import { memo, useRef, useState } from "react";

import { getActiveVersion } from "../state/thumbnailReducer";
import { PencilIcon, RefreshIcon, WandIcon } from "./icons";
import ThumbnailArt from "./ThumbnailArt";

const EDIT_IDEAS = [
  "Make the headline bigger",
  "Use brighter, warmer colors",
  "Add more contrast",
  "Simplify the background",
];

function describeOrigin(version, versions) {
  if (version.kind === "original") return "Original concept";
  const parent = versions.find((candidate) => candidate.id === version.parentId);
  const from = parent ? `v${parent.number}` : "an earlier version";
  return version.kind === "edit"
    ? `Edit of ${from}: “${version.prompt}”`
    : `Regenerated from ${from}`;
}

// memo: a card only re-renders when its own variation changes. That works
// because the callbacks from useThumbnailVariations never change identity.
const ThumbnailCard = memo(function ThumbnailCard({
  variation,
  position,
  onRegenerate,
  onEdit,
  onSelectVersion,
}) {
  const [editText, setEditText] = useState("");
  const [ideaIndex, setIdeaIndex] = useState(0);
  const editInput = useRef(null);

  const active = getActiveVersion(variation);
  const trimmed = editText.trim();

  async function handleSubmit(event) {
    event.preventDefault();
    if (!trimmed || variation.busy) return;

    // Only clear the box if the edit worked, so a failure keeps the text.
    const added = await onEdit(variation, trimmed);
    if (added) setEditText("");
  }

  function suggestIdea() {
    setEditText(EDIT_IDEAS[ideaIndex % EDIT_IDEAS.length]);
    setIdeaIndex((current) => current + 1);
    editInput.current?.focus();
  }

  return (
    <li className="cg-variation">
      <div className="cg-variation-art" aria-busy={variation.busy}>
        <ThumbnailArt headline={active.art.headline} palette={active.art.palette} />
        <span className="cg-version-badge">v{active.number}</span>
        {variation.busy && (
          <div className="cg-variation-busy" role="status">
            <span className="cg-spinner" aria-hidden="true" />
            Creating a new version…
          </div>
        )}
      </div>

      <h3>Variation {position}</h3>
      <p className="cg-origin">{describeOrigin(active, variation.versions)}</p>

      {variation.versions.length > 1 && (
        <div className="cg-versions" role="group" aria-label={`Versions of variation ${position}`}>
          {variation.versions.map((version) => (
            <button
              key={version.id}
              type="button"
              aria-pressed={version.id === active.id}
              onClick={() => onSelectVersion(variation.id, version.id)}
            >
              v{version.number}
            </button>
          ))}
        </div>
      )}

      <form className="cg-edit" onSubmit={handleSubmit}>
        <div className="cg-edit-row">
          <input
            ref={editInput}
            type="text"
            value={editText}
            maxLength={200}
            onChange={(event) => setEditText(event.target.value)}
            placeholder="Edit this image..."
            aria-label={`Describe an edit for variation ${position}`}
          />
          <button
            type="button"
            className="cg-icon-button"
            onClick={suggestIdea}
            aria-label="Suggest an edit idea"
            title="Suggest an edit idea"
          >
            <WandIcon size={18} />
          </button>
        </div>

        <div className="cg-edit-buttons">
          <button
            type="button"
            className="cg-button cg-button--soft"
            disabled={variation.busy}
            onClick={() => onRegenerate(variation)}
          >
            <RefreshIcon size={16} />
            Regenerate
          </button>
          <button
            type="submit"
            className="cg-button cg-button--outline"
            disabled={variation.busy || !trimmed}
          >
            <PencilIcon size={16} />
            Edit
          </button>
        </div>
      </form>

      {variation.error && (
        <p className="cg-problems" role="alert">
          {variation.error}
        </p>
      )}
    </li>
  );
});

export default ThumbnailCard;
