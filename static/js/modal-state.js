document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-modal-clear-query]").forEach((modalElement) => {
        modalElement.addEventListener("hidden.bs.modal", () => {
            const parameterNames = modalElement.dataset.modalClearQuery
                .split(/\s+/)
                .filter(Boolean);
            const url = new URL(window.location.href);
            let changed = false;

            parameterNames.forEach((name) => {
                if (url.searchParams.has(name)) {
                    url.searchParams.delete(name);
                    changed = true;
                }
            });

            if (changed) {
                window.history.replaceState(
                    window.history.state,
                    "",
                    `${url.pathname}${url.search}${url.hash}`,
                );
            }
        });
    });

    document.querySelectorAll("[data-modal-auto-open]").forEach((trigger) => {
        const modalId = trigger.dataset.modalAutoOpen || trigger.id;
        const modalElement = document.getElementById(modalId);
        if (modalElement) {
            bootstrap.Modal.getOrCreateInstance(modalElement).show();
        }
    });
});
