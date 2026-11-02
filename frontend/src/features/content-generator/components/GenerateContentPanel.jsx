import { useId } from "react";

import { ArrowRightIcon, HashIcon, ImageIcon, InfoIcon, ListIcon, SparklesIcon } from "./icons";

function ActionButton({ icon, label, note, primary, loading, disabled, describedBy, onClick }) {
  return (
    <button
      type="button"
      className={`cg-action${primary ? " cg-action--primary" : ""}`}
      disabled={disabled || loading}
      aria-busy={loading}
      aria-describedby={describedBy}
      onClick={onClick}
    >
      <span className="cg-action-icon">{icon}</span>
      <span className="cg-action-label">
        {loading ? "Generating…" : label}
        {note && !loading && <small>{note}</small>}
      </span>
      {loading ? <span className="cg-spinner" aria-hidden="true" /> : <ArrowRightIcon size={18} />}
    </button>
  );
}

function GenerateContentPanel({
  canGenerate,
  captionsLoading,
  hashtagsLoading,
  thumbnailsLoading,
  onCaptions,
  onHashtags,
  onThumbnails,
}) {
  const titleId = useId();
  const hintId = useId();

  // When the form is not ready, the buttons point at the sentence explaining why.
  const describedBy = canGenerate ? undefined : hintId;
  const disabled = !canGenerate;

  return (
    <section className="cg-card" aria-labelledby={titleId}>
      <header className="cg-card-head">
        <span className="cg-card-icon">
          <SparklesIcon />
        </span>
        <div>
          <h2 id={titleId}>Generate content</h2>
          <p>Create publishing assets from your video details.</p>
        </div>
      </header>

      <div className="cg-actions">
        <ActionButton
          primary
          icon={<ListIcon size={20} />}
          label="Generate captions"
          loading={captionsLoading}
          disabled={disabled}
          describedBy={describedBy}
          onClick={onCaptions}
        />
        <ActionButton
          icon={<HashIcon size={20} />}
          label="Generate hashtags & SEO keywords"
          loading={hashtagsLoading}
          disabled={disabled}
          describedBy={describedBy}
          onClick={onHashtags}
        />
        <ActionButton
          icon={<ImageIcon size={20} />}
          label="Generate thumbnails"
          note="3 variations"
          loading={thumbnailsLoading}
          disabled={disabled}
          describedBy={describedBy}
          onClick={onThumbnails}
        />
      </div>

      {!canGenerate && (
        <p id={hintId} className="cg-hint">
          Add a video topic to enable these actions.
        </p>
      )}

      <p className="cg-note">
        <InfoIcon size={16} />
        Preview mode: results are placeholders until the AI service is connected.
      </p>
    </section>
  );
}

export default GenerateContentPanel;
