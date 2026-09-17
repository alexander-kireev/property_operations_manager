document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.getElementById("eventWorkspace");
    const parameters = new URLSearchParams(window.location.search);

    if (workspace && parameters.get("tab") === "details" && parameters.has("selected")) {
        workspace.classList.add("show-detail");
    }

    const participationFilter = document.getElementById("eventParticipation");
    const presenceFilter = document.getElementById("eventPresence");
    const compatibilityNote = document.getElementById("eventFilterCompatibility");

    function updateFilterCompatibility() {
        if (!participationFilter || !presenceFilter) return;

        const participationNotRequired = participationFilter.value === "not_required";
        const presenceRequiredOption = presenceFilter.querySelector('option[value="required"]');
        if (presenceRequiredOption) presenceRequiredOption.disabled = participationNotRequired;
        if (participationNotRequired && presenceFilter.value === "required") presenceFilter.value = "";
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
        const startTime = form.querySelector('[name="start_time"]');
        const endTime = form.querySelector('[name="end_time"]');
        const participation = form.querySelector('[name="user_participation_required"]');
        const presence = form.querySelector('[name="user_presence_required"]');
        const presenceHelp = form.querySelector("[data-presence-help]");

        function updateTimeFields({clear = false} = {}) {
            if (!allDay || !startTime || !endTime) return;
            startTime.disabled = allDay.checked;
            endTime.disabled = allDay.checked;
            if (clear && allDay.checked) {
                startTime.value = "";
                endTime.value = "";
            }
        }

        function updatePresenceField() {
            if (!participation || !presence) return;
            presence.disabled = !participation.checked;
            if (!participation.checked) presence.checked = false;
            if (presenceHelp) {
                presenceHelp.textContent = participation.checked
                    ? ""
                    : "Participation must be required before presence can be required.";
            }
        }

        if (allDay) {
            allDay.addEventListener("change", () => updateTimeFields({clear: true}));
            updateTimeFields();
        }
        if (participation) {
            participation.addEventListener("change", updatePresenceField);
            updatePresenceField();
        }
    });

    const modalTrigger = document.querySelector("[data-open-event-modal]");
    if (modalTrigger) {
        const modal = document.getElementById(modalTrigger.dataset.openEventModal);
        if (modal) bootstrap.Modal.getOrCreateInstance(modal).show();
    }
});
