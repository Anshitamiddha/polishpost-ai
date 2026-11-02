import { useId } from "react";

import { ImageIcon, InfoIcon } from "./icons";
import ThumbnailCard from "./ThumbnailCard";

// `thumbnails` is the object returned by useThumbnailVariations.
function ThumbnailVariations({ thumbnails }) {
  const titleId = useId();
  const { variations, isGenerating, error, regenerate, edit, selectVersion } = thumbnails;

  return (
    <section className="cg-card" aria-labelledby={titleId}>
      <header className="cg-card-head">
        <span className="cg-card-icon">
          <ImageIcon />
        </span>
        <h2 id={titleId}>Thumbnail variations</h2>
        {variations.length > 0 && !isGenerating && (
          <span className="cg-chip">{variations.length} concepts</span>
        )}
      </header>

      {error && (
        <p className="cg-problems" role="alert">
          {error}
        </p>
      )}

      {isGenerating && (
        <ul className="cg-variation-grid" aria-busy="true" aria-label="Generating thumbnails">
          {[1, 2, 3].map((slot) => (
            <li key={slot} className="cg-skeleton" aria-hidden="true" />
          ))}
        </ul>
      )}

      {!isGenerating && variations.length > 0 && (
        <ul className="cg-variation-grid">
          {variations.map((variation, index) => (
            <ThumbnailCard
              key={variation.id}
              variation={variation}
              position={index + 1}
              onRegenerate={regenerate}
              onEdit={edit}
              onSelectVersion={selectVersion}
            />
          ))}
        </ul>
      )}

      {!isGenerating && variations.length === 0 && !error && (
        <p className="cg-empty">
          Add a video topic, then choose “Generate thumbnails”. Your concepts will appear here.
        </p>
      )}

      <p className="cg-note">
        <InfoIcon size={16} />
        Each edit creates a new version. Original images and previous versions stay available.
      </p>
    </section>
  );
}

export default ThumbnailVariations;
