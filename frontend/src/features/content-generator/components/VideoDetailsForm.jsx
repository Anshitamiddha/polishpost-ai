function VideoDetailsForm() {
  return (
    <section className="content-panel">
      <h2>Video details</h2>

      <p className="panel-description">
        Add the context needed to prepare your content.
      </p>

      <div className="form-field">
        <label htmlFor="video-title">
          Video topic or title
        </label>

        <input
          id="video-title"
          type="text"
          placeholder="e.g. Building my first AI project"
        />
      </div>

      <div className="form-field">
        <label htmlFor="video-description">
          Video description
        </label>

        <textarea
          id="video-description"
          rows={4}
          placeholder="Describe what happens in your video..."
        />
      </div>
    </section>
  );
}

export default VideoDetailsForm;
