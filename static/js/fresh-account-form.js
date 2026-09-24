// These sensitive account forms start blank, including after browser back/forward restore.
// Password managers can still offer a credential after the user focuses a field.
(() => {
    const form = document.querySelector("[data-fresh-account-form]");
    if (!form) return;

    const preserveRestoredEmail = form.hasAttribute("data-preserve-restored-email");
    const fields = [...form.querySelectorAll("input:not([type=hidden])")]
        .filter((field) => !(preserveRestoredEmail && field.name === "new_email"));
    const edited = new Set();
    const clearUntouched = () => {
        fields.forEach((field) => {
            if (!edited.has(field)) field.value = "";
        });
    };

    for (const field of fields) {
        for (const eventName of ["keydown", "beforeinput", "paste", "compositionstart"]) {
            field.addEventListener(eventName, () => edited.add(field));
        }
        field.addEventListener("input", () => {
            if (document.activeElement === field) edited.add(field);
        });
        field.addEventListener("focus", () => {
            if (!edited.has(field)) field.value = "";
        });
    }

    clearUntouched();
    window.addEventListener("pageshow", () => {
        edited.clear();
        clearUntouched();
        // Some browsers apply their saved form state just after pageshow.
        window.setTimeout(clearUntouched, 250);
        window.setTimeout(clearUntouched, 1000);
    });
})();
