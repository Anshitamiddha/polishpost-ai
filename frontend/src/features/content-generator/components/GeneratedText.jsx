import { useId } from "react";

import { CheckIcon, CopyIcon, ListIcon } from "./icons";

function CopyButton({ label, copied, onClick }) {
  return (
    <button type="button" className="cg-copy" onClick={onClick}>
      {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
      {copied ? "Copied" : label}
    </button>
  );
}

// `captions` and `hashtags` are the objects returned by useAsyncAction.
function GeneratedText({ captions, hashtags, copiedKey, onCopy }) {
  const titleId = useId();
  const hasAnything =
    captions.data || hashtags.data || captions.error || hashtags.error;

  // Nothing to show until the user has generated captions or hashtags.
  if (!hasAnything) return null;

  return (
    <section className="cg-card" aria-labelledby={titleId}>
      <header className="cg-card-head">
        <span className="cg-card-icon">
          <ListIcon />
        </span>
        <h2 id={titleId}>Generated text</h2>
      </header>

      {captions.error && (
        <p className="cg-problems" role="alert">
          Captions: {captions.error}
        </p>
      )}
      {captions.data && (
        <div className="cg-result" aria-busy={captions.isLoading}>
          <h3>Captions</h3>
          <ol className="cg-captions">
            {captions.data.map((caption, index) => (
              <li key={caption}>
                <p>{caption}</p>
                <CopyButton
                  label="Copy"
                  copied={copiedKey === `caption-${index}`}
                  onClick={() => onCopy(caption, `caption-${index}`)}
                />
              </li>
            ))}
          </ol>
        </div>
      )}

      {hashtags.error && (
        <p className="cg-problems" role="alert">
          Hashtags: {hashtags.error}
        </p>
      )}
      {hashtags.data && (
        <div className="cg-result" aria-busy={hashtags.isLoading}>
          <div className="cg-result-head">
            <h3>Hashtags</h3>
            <CopyButton
              label="Copy all"
              copied={copiedKey === "hashtags"}
              onClick={() => onCopy(hashtags.data.join(" "), "hashtags")}
            />
          </div>
          <ul className="cg-hashtags">
            {hashtags.data.map((tag) => (
              <li key={tag}>{tag}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export default GeneratedText;
