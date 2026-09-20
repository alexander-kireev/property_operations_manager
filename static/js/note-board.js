document.addEventListener("click", (event) => {
    const editButton = event.target.closest("[data-note-edit-toggle]");
    const cancelButton = event.target.closest("[data-note-edit-cancel]");

    if (!editButton && !cancelButton) return;

    const note = event.target.closest("[data-note]");
    if (!note) return;

    const display = note.querySelector("[data-note-display]");
    const editor = note.querySelector("[data-note-edit]");
    const toggle = note.querySelector("[data-note-edit-toggle]");
    if (!display || !editor || !toggle) return;

    const isEditing = Boolean(editButton);
    display.hidden = isEditing;
    editor.hidden = !isEditing;
    toggle.setAttribute("aria-expanded", String(isEditing));

    if (isEditing) {
        editor.querySelector("textarea")?.focus();
    } else {
        toggle.focus();
    }
});
