import { useState } from "react";

import Modal from "./Modal";

// Mirrors CreateWorkspaceRequest on the backend (@Size(max = 100)).
const MAX_NAME_LENGTH = 100;

function CreateWorkspaceModal({ onCreate, onClose }) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    const cleanName = name.trim();

    if (!cleanName) {
      setError("Workspace name is required.");
      return;
    }

    setError("");
    setIsSaving(true);

    try {
      await onCreate(cleanName);
      onClose();
    } catch (err) {
      setError(err.message || "Couldn't create the workspace. Please try again.");
      setIsSaving(false);
    }
  }

  return (
    <Modal title="Create workspace" onClose={onClose} isBusy={isSaving}>
      <p className="ws-modal-hint">
        A workspace is where you and your team create and publish content
        together. You'll be its owner and can add members afterwards.
      </p>

      <form className="ws-modal-form" onSubmit={handleSubmit}>
        <label htmlFor="workspace-name">Workspace name</label>
        <input
          id="workspace-name"
          name="name"
          type="text"
          placeholder="e.g. Gaming Channel"
          maxLength={MAX_NAME_LENGTH}
          autoComplete="off"
          autoFocus
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />

        {error && (
          <p className="ws-modal-error" role="alert">
            {error}
          </p>
        )}

        <div className="ws-modal-actions">
          <button
            type="button"
            className="ws-button secondary"
            onClick={onClose}
            disabled={isSaving}
          >
            Cancel
          </button>

          <button
            type="submit"
            className="ws-button primary"
            disabled={isSaving}
            aria-busy={isSaving}
          >
            {isSaving ? "Creating..." : "Create workspace"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default CreateWorkspaceModal;
