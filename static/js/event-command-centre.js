document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.getElementById("eventWorkspace");
    const parameters = new URLSearchParams(window.location.search);

    if (workspace && parameters.get("open") === "detail" && parameters.has("selected")) {
        workspace.classList.add("show-detail");
    }

    document.querySelectorAll("[data-calendar-day-href]").forEach((day) => {
        const mobileDayHref = (href) => window.matchMedia("(max-width: 767.98px)").matches
            ? href.replace("#eventResults", "#eventAgenda") : href;
        day.addEventListener("click", (event) => {
            const dateLink = event.target.closest(".event-calendar-day-number");
            if (dateLink && window.matchMedia("(max-width: 767.98px)").matches) {
                event.preventDefault();
                window.location.assign(mobileDayHref(dateLink.href));
                return;
            }
            if (event.target.closest("a, button")) return;
            window.location.assign(mobileDayHref(day.dataset.calendarDayHref));
        });
    });

    document.querySelectorAll(".event-command-entry > [data-workspace-scroll-row]").forEach((row) => {
        row.addEventListener("click", (event) => {
            if (!window.matchMedia("(max-width: 767.98px)").matches
                || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            const expanded = row.nextElementSibling;
            if (expanded?.classList.contains("event-mobile-expanded")) {
                event.preventDefault();
                expanded.hidden = !expanded.hidden;
                row.setAttribute("aria-expanded", String(!expanded.hidden));
            } else {
                event.preventDefault();
                window.location.assign(`${row.href}#${row.parentElement.id}`);
            }
        });
    });

    document.querySelectorAll(".event-mobile-agenda-row").forEach((row) => {
        row.addEventListener("click", (event) => {
            if (!window.matchMedia("(max-width: 767.98px)").matches
                || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
            const selected = new URL(row.href).searchParams.get("selected");
            if (!selected) return;
            event.preventDefault();
            window.location.assign(`${row.href}#eventRow${selected}`);
        });
    });

    const participationFilter = document.getElementById("eventParticipation");
    const presenceFilter = document.getElementById("eventPresence");
    const compatibilityNote = document.getElementById("eventFilterCompatibility");

    function updateFilterCompatibility() {
        if (!participationFilter || !presenceFilter) return;

        const participationNotRequired = participationFilter.value === "not_required";
        const presenceRequiredOption = presenceFilter.querySelector('option[value="required"]');
        if (presenceRequiredOption) presenceRequiredOption.disabled = participationNotRequired;
        if (participationNotRequired && presenceFilter.value === "required") {
            presenceFilter.value = "";
            window.SearchableSelect?.refresh(presenceFilter);
        }
        if (compatibilityNote) {
            compatibilityNote.textContent = participationNotRequired
                ? "Presence cannot be required when participation is not required."
                : "";
        }
    }

    if (participationFilter) {
        participationFilter.addEventListener("change", updateFilterCompatibility);
        updateFilterCompatibility();
    }

    document.querySelectorAll("[data-event-form]").forEach((form) => {
        const allDay = form.querySelector('[name="all_day"]');
        const durationChoices = [...form.querySelectorAll("[data-duration-choice]")];
        const startTime = form.querySelector('[name="start_time"]');
        const endTime = form.querySelector('[name="end_time"]');
        const participation = form.querySelector('[name="user_participation_required"]');
        const presence = form.querySelector('[name="user_presence_required"]');

        function updateTimeFields({clear = false} = {}) {
            if (!allDay || !startTime || !endTime) return;
            startTime.disabled = allDay.checked;
            endTime.disabled = allDay.checked;
            durationChoices.forEach((choice) => {
                choice.checked = (choice.value === "all_day") === allDay.checked;
            });
            if (clear && allDay.checked) {
                startTime.value = "";
                endTime.value = "";
            }
        }

        function updatePresenceField() {
            if (!participation || !presence) return;
            presence.disabled = !participation.checked;
            if (!participation.checked) presence.checked = false;
        }

        if (allDay) {
            allDay.addEventListener("change", () => updateTimeFields({clear: true}));
            durationChoices.forEach((choice) => {
                choice.addEventListener("change", () => {
                    allDay.checked = choice.value === "all_day";
                    allDay.dispatchEvent(new Event("change", {bubbles: true}));
                });
            });
            updateTimeFields();
        }
        if (participation) {
            participation.addEventListener("change", updatePresenceField);
            updatePresenceField();
        }
    });

    document.querySelectorAll("[data-event-tabs]").forEach((form) => {
        const tabs = [...form.querySelectorAll("[data-event-tab]")];
        const panels = [...form.querySelectorAll("[data-event-panel]")];
        const body = form.querySelector(".event-form-body");

        function activateTab(name, {focus = false} = {}) {
            tabs.forEach((tab) => {
                const active = tab.dataset.eventTab === name;
                tab.classList.toggle("is-active", active);
                tab.setAttribute("aria-selected", String(active));
                tab.tabIndex = active ? 0 : -1;
                if (active && focus) tab.focus();
            });
            panels.forEach((panel) => {
                panel.hidden = panel.dataset.eventPanel !== name;
            });
            if (body) body.scrollTop = 0;
        }

        tabs.forEach((tab, index) => {
            tab.addEventListener("click", () => activateTab(tab.dataset.eventTab));
            tab.addEventListener("keydown", (event) => {
                let next = null;
                if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
                if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
                if (event.key === "Home") next = tabs[0];
                if (event.key === "End") next = tabs[tabs.length - 1];
                if (next) {
                    event.preventDefault();
                    activateTab(next.dataset.eventTab, {focus: true});
                }
            });
        });

        form.addEventListener("invalid", (event) => {
            const panel = event.target.closest("[data-event-panel]");
            if (panel?.hidden) activateTab(panel.dataset.eventPanel);
        }, true);

        activateTab(tabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.dataset.eventTab || "details");
    });

    document.querySelectorAll("[data-contact-picker]").forEach((picker) => {
        const search = picker.querySelector("[data-contact-search]");
        const options = [...picker.querySelectorAll("[data-contact-option]")];
        const empty = picker.querySelector("[data-contact-empty]");
        const status = picker.querySelector("[data-contact-picker-status]");
        const tabCount = picker.closest(".modal")?.querySelector("[data-contact-tab-count]");

        function updatePicker() {
            const query = search?.value.trim().toLocaleLowerCase() || "";
            let visible = 0;
            let selected = 0;

            options.forEach((option) => {
                const checkbox = option.querySelector('input[type="checkbox"]');
                const matches = (option.dataset.searchText || option.textContent).toLocaleLowerCase().includes(query);
                option.hidden = !matches;
                if (matches) visible += 1;
                if (checkbox?.checked) selected += 1;
            });

            if (empty) empty.hidden = !query || visible > 0 || options.length === 0;
            if (status) status.textContent = `${selected} selected${query ? ` · ${visible} matching` : ""}`;
            if (tabCount) tabCount.textContent = selected;
        }

        search?.addEventListener("input", updatePicker);
        search?.addEventListener("keydown", (event) => {
            if (event.key === "Enter") event.preventDefault();
        });
        picker.addEventListener("change", updatePicker);
        updatePicker();
    });

});
