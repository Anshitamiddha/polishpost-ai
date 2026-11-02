import { useId } from "react";

import { useDropZone } from "../hooks/useDropZone";
import {
  ACCEPTED_IMAGE_TYPES,
  MAX_IMAGE_MB,
  MAX_REFERENCE_IMAGES,
} from "../lib/referenceImageRules";
import { CloseIcon, ImageIcon, UploadCloudIcon } from "./icons";

function ReferenceImagesPanel({ images, problems, isFull, onAddFiles, onRemove }) {
  const titleId = useId();
  const { isDragging, dropProps } = useDropZone(onAddFiles);

  function handleChosen(event) {
    onAddFiles(Array.from(event.target.files));
    // Clear the input, or choosing the same file again would do nothing.
    event.target.value = "";
  }

  return (
    <section className="cg-card" aria-labelledby={titleId}>
      <header className="cg-card-head">
        <span className="cg-card-icon">
          <ImageIcon />
        </span>
        <div>
          <h2 id={titleId}>Reference images</h2>
          <p>Upload one or more images to guide your thumbnail.</p>
        </div>
        {images.length > 0 && (
          <span className="cg-chip">
            {images.length} of {MAX_REFERENCE_IMAGES}
          </span>
        )}
      </header>

      {/* The real input sits inside the label, hidden but still focusable, so
          the whole zone works with a click, a drop, or the keyboard. */}
      <label
        className="cg-dropzone"
        data-dragging={isDragging}
        data-full={isFull}
        {...dropProps}
      >
        <input
          className="cg-visually-hidden"
          type="file"
          multiple
          accept={ACCEPTED_IMAGE_TYPES.join(",")}
          disabled={isFull}
          onChange={handleChosen}
        />
        <UploadCloudIcon size={30} />
        {isFull ? (
          <strong>You have added the maximum of {MAX_REFERENCE_IMAGES} images</strong>
        ) : (
          <strong>
            {isDragging ? "Drop to add" : "Drop images here"}{" "}
            {!isDragging && <span className="cg-link">or browse</span>}
          </strong>
        )}
        <span className="cg-hint">
          PNG, JPG, WEBP · Up to {MAX_REFERENCE_IMAGES} images · {MAX_IMAGE_MB} MB each
        </span>
      </label>

      {problems.length > 0 && (
        <ul className="cg-problems" role="alert">
          {problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}

      {images.length > 0 && (
        <ul className="cg-reference-grid">
          {images.map((image, index) => (
            <li key={image.id} className="cg-reference">
              <img src={image.url} alt={`Reference ${index + 1}: ${image.file.name}`} />
              <span className="cg-reference-label">Reference {index + 1}</span>
              <button
                type="button"
                className="cg-reference-remove"
                aria-label={`Remove reference ${index + 1}`}
                onClick={() => onRemove(image.id)}
              >
                <CloseIcon size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default ReferenceImagesPanel;
