document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-contact-method-form]").forEach((form) => {
        const method = form.querySelector('[name="type"]');
        const value = form.querySelector('[name="value"]');
        const label = form.querySelector("[data-contact-method-value-label]");
        const help = form.querySelector("[data-contact-method-help]");
        if (!method || !value || !label || !help) return;

        function update() {
            const isEmail = method.value === "email";
            const isTelephone = method.value === "telephone";
            label.textContent = isEmail ? "Email address" : isTelephone ? "Telephone number" : "Contact information";
            value.type = isEmail ? "email" : isTelephone ? "tel" : "text";
            value.placeholder = isEmail ? "name@example.com" : isTelephone ? "+44 7700 900123" : "";
            value.inputMode = isTelephone ? "tel" : "";
            help.hidden = !isTelephone;
        }

        method.addEventListener("change", update);
        update();
    });
});
