import { useId } from "react";

import { previewSource } from "../lib/thumbnailPreview";
import { ImageIcon, InfoIcon } from "./icons";

// `thumbnails` is the object returned by useThumbnailGeneration. It holds at
// most one thumbnail: the one the last successful generation returned.
function ThumbnailPreview({ thumbnails }) {
  const titleId = useId();
  const { isGenerating, error, thumbnail } = thumbnails;
  const source = previewSource(thumbnail);

  return (
    <section className="cg-card" aria-labelledby={titleId}>
      <header className="cg-card-head">
        <span className="cg-card-icon">
          <ImageIcon />
        </span>
        <h2 id={titleId}>Thumbnail</h2>
      </header>

      {error && (
        <p className="cg-problems" role="alert">
          {error}
        </p>
      )}

      {isGenerating && (
        <div className="cg-skeleton" role="status" aria-label="Generating thumbnail" />
      )}

      {!isGenerating && source && (
        <div className="cg-thumbnail">
          {/* The key gives every new thumbnail a fresh image, so the old one never lingers. */}
          <img
            key={thumbnail.image.assetId}
            src={source}
            width={thumbnail.image.width}
            height={thumbnail.image.height}
            alt="The newly generated thumbnail"
          />
        </div>
      )}

      {!isGenerating && thumbnail && !source && (
        <p className="cg-empty">The thumbnail was created, but its preview is not available.</p>
      )}

      {!isGenerating && !thumbnail && !error && (
        <p className="cg-empty">
          Add a video topic, then choose “Generate thumbnail”. Your thumbnail will appear here.
        </p>
      )}

      <p className="cg-note">
        <InfoIcon size={16} />
        Generating again replaces this thumbnail.
      </p>
    </section>
  );
}

export default ThumbnailPreview;
