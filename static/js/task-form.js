document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-task-form]").forEach((form) => {
        const scheduledDate = form.querySelector('[name="scheduled_date"]');
        const completionDeadline = form.querySelector('[name="completion_deadline"]');
        const dateWarning = form.querySelector('[data-task-date-warning]');

        function updateDateWarning() {
            if (scheduledDate && completionDeadline && dateWarning) {
                dateWarning.hidden = !(
                    scheduledDate.value && completionDeadline.value &&
                    completionDeadline.value < scheduledDate.value
                );
            }
        }

        [scheduledDate, completionDeadline].forEach((field) => {
            field?.addEventListener("input", updateDateWarning);
            field?.addEventListener("change", updateDateWarning);
        });
        updateDateWarning();

        const relationshipFieldset = form.querySelector("[data-task-relationship]");

        if (!relationshipFieldset) {
            return;
        }

        const relationshipChoices = relationshipFieldset.querySelectorAll(
            'input[name="relationship_type"]'
        );
        const standalonePanel = relationshipFieldset.querySelector(
            '[data-relationship-panel="standalone"]'
        );
        const propertyPanel = relationshipFieldset.querySelector(
            '[data-relationship-panel="property"]'
        );
        const issuePanel = relationshipFieldset.querySelector(
            '[data-relationship-panel="issue"]'
        );
        const propertySelect = propertyPanel.querySelector("select");
        const issueSelect = issuePanel.querySelector("select");

        function selectedRelationshipType() {
            const selectedChoice = relationshipFieldset.querySelector(
                'input[name="relationship_type"]:checked'
            );

            if (selectedChoice) {
                return selectedChoice.value;
            }

            if (propertySelect.value) {
                return "property";
            }

            if (issueSelect.value) {
                return "issue";
            }

            return "standalone";
        }

        function updateRelationshipFields({clearInactive = false} = {}) {
            const relationshipType = selectedRelationshipType();
            const showProperty = relationshipType === "property";
            const showIssue = relationshipType === "issue";

            standalonePanel.hidden = relationshipType !== "standalone";
            propertyPanel.hidden = !showProperty;
            issuePanel.hidden = !showIssue;
            propertySelect.disabled = !showProperty;
            issueSelect.disabled = !showIssue;

            if (clearInactive && !showProperty) {
                propertySelect.value = "";
            }

            if (clearInactive && !showIssue) {
                issueSelect.value = "";
            }

            window.SearchableSelect?.refresh(propertySelect);
            window.SearchableSelect?.refresh(issueSelect);
        }

        relationshipChoices.forEach((choice) => {
            choice.addEventListener("change", () => {
                updateRelationshipFields({clearInactive: true});
            });
        });

        updateRelationshipFields();
    });
});
