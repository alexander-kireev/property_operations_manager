document.addEventListener("DOMContentLoaded", () => {
    const commandCentre = document.querySelector(".task-command-centre");

    if (!commandCentre) {
        return;
    }

    const filterForm = document.getElementById("taskFilterForm");
    if (filterForm) {
        filterForm.querySelectorAll("[data-clear-task-filter]").forEach((button) => {
            button.addEventListener("click", () => {
                const field = filterForm.elements.namedItem(
                    button.dataset.clearTaskFilter
                );
                if (field) {
                    field.value = "";
                    filterForm.requestSubmit();
                }
            });
        });
    }
});
