import { useId } from "react";

import CharacterCounter from "./CharacterCounter";
import { LightbulbIcon } from "./icons";

// `prompt` is the object returned by useLimitedText.
function PromptPanel({ prompt }) {
  const titleId = useId();
  const counterId = useId();

  return (
    <section className="cg-card" aria-labelledby={titleId}>
      <header className="cg-card-head">
        <span className="cg-card-icon">
          <LightbulbIcon />
        </span>
        <div>
          <h2 id={titleId}>Global creative prompt</h2>
          <p>Applies to every generated thumbnail and its revisions.</p>
        </div>
      </header>

      <div className="cg-field">
        <textarea
          rows={3}
          aria-labelledby={titleId}
          aria-describedby={counterId}
          maxLength={prompt.maxLength}
          value={prompt.value}
          onChange={prompt.onChange}
          placeholder="Describe the style every thumbnail should share..."
        />
        <CharacterCounter id={counterId} length={prompt.length} max={prompt.maxLength} />
      </div>
    </section>
  );
}

export default PromptPanel;
