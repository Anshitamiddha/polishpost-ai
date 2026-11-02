import { useId } from "react";

import CharacterCounter from "./CharacterCounter";
import { VideoIcon } from "./icons";

// `topic` and `description` are the objects returned by useLimitedText.
function VideoDetailsForm({ topic, description }) {
  const titleId = useId();
  const topicId = useId();
  const descriptionId = useId();
  const counterId = useId();

  return (
    <section className="cg-card" aria-labelledby={titleId}>
      <header className="cg-card-head">
        <span className="cg-card-icon">
          <VideoIcon />
        </span>
        <h2 id={titleId}>Video details</h2>
      </header>

      <div className="cg-field">
        <label htmlFor={topicId}>
          Video topic or title <span className="cg-required">Required</span>
        </label>
        <input
          id={topicId}
          type="text"
          required
          maxLength={topic.maxLength}
          value={topic.value}
          onChange={topic.onChange}
          placeholder="e.g. I built an AI app in 7 days"
        />
      </div>

      <div className="cg-field">
        <label htmlFor={descriptionId}>What is this video about?</label>
        <textarea
          id={descriptionId}
          rows={4}
          aria-describedby={counterId}
          maxLength={description.maxLength}
          value={description.value}
          onChange={description.onChange}
          placeholder="Describe the video, audience, and key takeaway..."
        />
        <CharacterCounter
          id={counterId}
          length={description.length}
          max={description.maxLength}
        />
      </div>
    </section>
  );
}

export default VideoDetailsForm;
