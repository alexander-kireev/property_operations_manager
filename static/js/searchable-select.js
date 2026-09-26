document.addEventListener("DOMContentLoaded", () => {
    const controls = new WeakMap();
    let openControl = null;
    let nextId = 0;

    function initialize(root = document) {
    root.querySelectorAll("select.form-select:not([multiple])").forEach((select) => {
        if (controls.has(select) || select.hasAttribute("data-native-select") || select.size > 1) return;
        const listeners = new AbortController();

        let wrapper = select.closest("[data-searchable-select]");
        if (!wrapper) {
            wrapper = document.createElement("div");
            select.before(wrapper);
            wrapper.append(select);
        }
        wrapper.classList.add("app-select");

        if (!select.id) select.id = `app_select_${nextId++}`;
        const label = [...document.querySelectorAll("label[for]")].find(
            (candidate) => candidate.htmlFor === select.id
        );
        const modal = wrapper.closest(".modal, dialog");
        let options = [...select.options];
        const searchable = wrapper.hasAttribute("data-searchable-select") ||
            ["property", "issue"].includes(select.name) || options.length > 12;
        const trigger = document.createElement("button");
        const popup = document.createElement("div");
        const results = document.createElement("div");
        const search = searchable ? document.createElement("input") : null;
        let visibleOptions = [];
        let activeIndex = -1;
        let typeahead = "";
        let typeaheadTimer;

        trigger.type = "button";
        trigger.id = `${select.id}_control`;
        trigger.className = `${select.className} app-select-trigger`;
        if (!searchable) trigger.setAttribute("role", "combobox");
        trigger.setAttribute("aria-haspopup", "listbox");
        trigger.setAttribute("aria-controls", `${select.id}_options`);
        trigger.setAttribute("aria-expanded", "false");
        if (select.hasAttribute("aria-label")) {
            trigger.setAttribute("aria-label", select.getAttribute("aria-label"));
        }

        popup.className = "app-select-popup";
        popup.hidden = true;
        results.id = `${select.id}_options`;
        results.className = "app-select-results";
        results.setAttribute("role", "listbox");

        if (search) {
            search.type = "search";
            search.className = "form-control form-control-sm app-select-search";
            search.autocomplete = "off";
            search.placeholder = "Search choices";
            search.setAttribute("role", "combobox");
            search.setAttribute("aria-label", `Search ${label?.textContent.trim() || select.name || "choices"}`);
            search.setAttribute("aria-autocomplete", "list");
            search.setAttribute("aria-controls", results.id);
            search.setAttribute("aria-expanded", "true");
            popup.append(search);
        }
        popup.append(results);

        function sync() {
            options = [...select.options];
            const selected = select.selectedOptions[0];
            trigger.textContent = selected?.textContent.trim() || "Choose an option";
            trigger.title = trigger.textContent;
            trigger.disabled = select.disabled;
            if (select.disabled) close();
        }

        function positionPopup() {
            if (popup.hidden) return;
            const anchor = trigger.getBoundingClientRect();
            const spaceBelow = window.innerHeight - anchor.bottom - 8;
            const spaceAbove = anchor.top - 8;
            const openAbove = spaceBelow < 240 && spaceAbove > spaceBelow;
            const available = openAbove ? spaceAbove : spaceBelow;
            const width = Math.min(anchor.width, window.innerWidth - 16);

            popup.style.width = `${width}px`;
            popup.style.left = `${Math.max(8, Math.min(anchor.left, window.innerWidth - width - 8))}px`;
            popup.style.maxHeight = `${Math.max(0, Math.min(240, available - 4))}px`;
            popup.style.top = openAbove
                ? `${anchor.top - popup.offsetHeight - 4}px`
                : `${anchor.bottom + 4}px`;
        }

        function markActive(index) {
            activeIndex = index;
            const focusOwner = search || trigger;
            results.querySelectorAll('[role="option"]').forEach((item, itemIndex) => {
                const active = itemIndex === index;
                item.classList.toggle("is-active", active);
                if (active) {
                    focusOwner.setAttribute("aria-activedescendant", item.id);
                    item.scrollIntoView({block: "nearest"});
                }
            });
            if (index < 0) focusOwner.removeAttribute("aria-activedescendant");
        }

        function nextEnabled(direction) {
            const start = activeIndex < 0 ? (direction > 0 ? -1 : 0) : activeIndex;
            for (let step = 1; step <= visibleOptions.length; step += 1) {
                const index = (start + direction * step + visibleOptions.length * 2) % visibleOptions.length;
                if (!visibleOptions[index].disabled) return index;
            }
            return -1;
        }

        function choose(option) {
            if (option.disabled) return;
            select.value = option.value;
            select.dispatchEvent(new Event("change", {bubbles: true}));
            close({restoreFocus: true});
        }

        function render(query = "") {
            const needle = query.trim().toLocaleLowerCase();
            visibleOptions = options.filter((option) =>
                option.textContent.toLocaleLowerCase().includes(needle)
            );
            results.replaceChildren();

            if (!visibleOptions.length) {
                const empty = document.createElement("div");
                empty.className = "app-select-empty";
                empty.textContent = "No matching choices";
                results.append(empty);
            } else {
                visibleOptions.forEach((option, index) => {
                    const item = document.createElement("div");
                    item.id = `${results.id}_${index}`;
                    item.className = "app-select-option";
                    item.setAttribute("role", "option");
                    item.setAttribute("aria-selected", String(option.value === select.value));
                    item.setAttribute("aria-disabled", String(option.disabled));
                    item.classList.toggle("is-selected", option.value === select.value);
                    item.classList.toggle("is-disabled", option.disabled);
                    item.textContent = option.textContent.trim();
                    item.title = item.textContent;
                    item.addEventListener("pointerdown", (event) => event.preventDefault());
                    item.addEventListener("click", () => choose(option));
                    results.append(item);
                });
            }
            const selectedIndex = visibleOptions.findIndex((option) => option.value === select.value);
            const firstMatch = visibleOptions.findIndex((option) => !option.disabled);
            markActive(needle ? firstMatch : selectedIndex);
            positionPopup();
        }

        function open() {
            if (trigger.disabled || !popup.hidden) return;
            openControl?.close();
            openControl = {close};
            popup.hidden = false;
            trigger.setAttribute("aria-expanded", "true");
            if (search) search.value = "";
            render();
            if (search) search.focus();
            else trigger.focus();
        }

        function close({restoreFocus = false} = {}) {
            if (popup.hidden) return;
            popup.hidden = true;
            trigger.setAttribute("aria-expanded", "false");
            trigger.removeAttribute("aria-activedescendant");
            search?.removeAttribute("aria-activedescendant");
            if (openControl?.close === close) openControl = null;
            if (restoreFocus) trigger.focus();
        }

        function moveFocusFromSearch(event) {
            const root = modal || document;
            const focusable = [...root.querySelectorAll(
                'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )].filter((element) => element !== search && element !== select &&
                !popup.contains(element) && element.getClientRects().length);
            const index = focusable.indexOf(trigger);
            const next = focusable[index + (event.shiftKey ? -1 : 1)];
            if (next) {
                event.preventDefault();
                close();
                next.focus();
            } else {
                close({restoreFocus: true});
            }
        }

        function handleNavigation(event) {
            if (event.key === "Escape" && !popup.hidden) {
                event.preventDefault();
                event.stopPropagation();
                close({restoreFocus: true});
            } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                open();
                if (visibleOptions.length) markActive(nextEnabled(event.key === "ArrowDown" ? 1 : -1));
            } else if (event.key === "Enter" && !popup.hidden) {
                event.preventDefault();
                if (activeIndex >= 0) choose(visibleOptions[activeIndex]);
            } else if (event.key === "Tab" && !popup.hidden) {
                if (search) moveFocusFromSearch(event);
                else close();
            }
        }

        trigger.addEventListener("click", () => popup.hidden ? open() : close(), {signal: listeners.signal});
        trigger.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                if (popup.hidden) open();
                else if (activeIndex >= 0) choose(visibleOptions[activeIndex]);
                return;
            }
            handleNavigation(event);
            if (!popup.hidden && !search && event.key.length === 1 && !event.ctrlKey && !event.altKey) {
                clearTimeout(typeaheadTimer);
                typeahead += event.key.toLocaleLowerCase();
                typeaheadTimer = setTimeout(() => { typeahead = ""; }, 600);
                const match = visibleOptions.findIndex((option) =>
                    !option.disabled && option.textContent.trim().toLocaleLowerCase().startsWith(typeahead)
                );
                if (match >= 0) markActive(match);
            }
        }, {signal: listeners.signal});
        search?.addEventListener("input", () => render(search.value), {signal: listeners.signal});
        search?.addEventListener("keydown", handleNavigation, {signal: listeners.signal});
        document.addEventListener("pointerdown", (event) => {
            if (!wrapper.contains(event.target) && !popup.contains(event.target)) close();
        }, {signal: listeners.signal});
        document.addEventListener("scroll", (event) => {
            if (event.target !== results) positionPopup();
        }, {capture: true, signal: listeners.signal});
        window.addEventListener("resize", positionPopup, {signal: listeners.signal});
        modal?.addEventListener(modal.tagName === "DIALOG" ? "close" : "hidden.bs.modal", close, {signal: listeners.signal});
        select.addEventListener("change", sync, {signal: listeners.signal});

        wrapper.append(trigger);
        (modal || document.body).append(popup);
        select.style.display = "none";
        select.tabIndex = -1;
        select.setAttribute("aria-hidden", "true");
        if (label) label.htmlFor = trigger.id;
        sync();
        controls.set(select, {
            refresh() { sync(); if (!popup.hidden) render(search?.value || ""); },
            destroy() {
                close();
                listeners.abort();
                popup.remove();
                trigger.remove();
                select.style.display = "";
                select.removeAttribute("aria-hidden");
                select.removeAttribute("tabindex");
                if (label) label.htmlFor = select.id;
            },
        });
    });
    }

    window.SearchableSelect = {
        init: initialize,
        refresh(select) {
            controls.get(select)?.refresh();
        },
        destroyWithin(root) {
            root.querySelectorAll("select.form-select:not([multiple])").forEach((select) => {
                controls.get(select)?.destroy();
                controls.delete(select);
            });
        },
    };
    initialize();
});
