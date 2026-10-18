import { useState } from "react";

import Modal from "./Modal";

// Adds someone to ONE specific workspace (the `workspace` prop), which is
// not necessarily the one currently selected in the sidebar.
function AddMemberModal({ workspace, onAdd, onClose }) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    const cleanEmail = email.trim();

    setError("");
    setNotice("");
    setIsSaving(true);

    try {
      await onAdd(workspace.id, cleanEmail);

      // Stay open so several people can be added in a row.
      setNotice(`${cleanEmail} was added to ${workspace.name}.`);
      setEmail("");
    } catch (err) {
      setError(err.message || "Couldn't add that member. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal title="Add member" onClose={onClose} isBusy={isSaving}>
      <p className="ws-modal-hint">
        Add someone to <strong>{workspace.name}</strong>. They need a
        PublishPro-AI account already, and they join as an Editor.
      </p>

      <form className="ws-modal-form" onSubmit={handleSubmit}>
        <label htmlFor="member-email">Email address</label>
        <input
          id="member-email"
          name="email"
          type="email"
          placeholder="teammate@example.com"
          autoComplete="off"
          autoFocus
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />

        {error && (
          <p className="ws-modal-error" role="alert">
            {error}
          </p>
        )}

        {notice && (
          <p className="ws-modal-success" role="status">
            <span aria-hidden="true">✓</span> {notice}
          </p>
        )}

        <div className="ws-modal-actions">
          <button
            type="button"
            className="ws-button secondary"
            onClick={onClose}
            disabled={isSaving}
          >
            Done
          </button>

          <button
            type="submit"
            className="ws-button primary"
            disabled={isSaving}
            aria-busy={isSaving}
          >
            {isSaving ? "Adding..." : "Add member"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export default AddMemberModal;
