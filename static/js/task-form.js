document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-task-form]").forEach((form) => {
        const relationshipFieldset = form.querySelector("[data-task-relationship]");

        if (!relationshipFieldset) {
            return;
        }

        const relationshipChoices = relationshipFieldset.querySelectorAll(
            'input[name="relationship_type"]'
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
        }

        relationshipChoices.forEach((choice) => {
            choice.addEventListener("change", () => {
                updateRelationshipFields({clearInactive: true});
            });
        });

        updateRelationshipFields();
    });
});
