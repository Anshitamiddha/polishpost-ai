import { useEffect, useId, useRef } from "react";

import "./workspace.css";

// Shared dialog shell: backdrop, title, close button, Escape to close and a
// Tab key that stays inside the dialog. `isBusy` blocks closing while a
// request is in flight.
function Modal({ title, onClose, isBusy = false, children }) {
  const titleId = useId();
  const dialogRef = useRef(null);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape" && !isBusy) {
        onClose();
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isBusy, onClose]);

  function handleTab(event) {
    if (event.key !== "Tab") {
      return;
    }

    const focusable = dialogRef.current.querySelectorAll(
      "input:not([disabled]), button:not([disabled])"
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      className="ws-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isBusy) {
          onClose();
        }
      }}
    >
      <div
        ref={dialogRef}
        className="ws-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={handleTab}
      >
        <div className="ws-modal-header">
          <h2 id={titleId}>{title}</h2>

          <button
            type="button"
            className="ws-modal-close"
            aria-label="Close"
            onClick={onClose}
            disabled={isBusy}
          >
            ×
          </button>
        </div>

        {children}
      </div>
    </div>
  );
}

export default Modal;
