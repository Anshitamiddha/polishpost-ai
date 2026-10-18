function UploadPanel() {
  return (
    <section className="content-panel upload-panel">
      <h2>Upload your video</h2>

      <p className="panel-description">
        Choose a video to prepare its content.
      </p>

      <label className="upload-dropzone">
        <input
          type="file"
          accept="video/*"
          hidden
        />

        <span className="upload-icon" aria-hidden="true">
          ↑
        </span>

        <strong>Click to select a video</strong>
        <span>MP4, MOV or WebM</span>
      </label>
    </section>
  );
}

export default UploadPanel;
