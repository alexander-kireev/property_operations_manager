document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.getElementById("issueWorkspace");
    const parameters = new URLSearchParams(window.location.search);

    if (workspace && parameters.has("selected")) {
        workspace.classList.add("show-detail");
    }

    document.querySelectorAll("[data-no-task-toggle]").forEach((element) => {
        element.addEventListener("click", (event) => event.stopPropagation());
    });

    const editForm = document.getElementById("editIssueTaskForm");
    document.querySelectorAll(".issue-edit-task").forEach((button) => {
        button.addEventListener("click", () => {
            if (!editForm) {
                return;
            }

            editForm.action = button.dataset.action;
            editForm.querySelector('[name="title"]').value = button.dataset.title;
            editForm.querySelector('[name="description"]').value = button.dataset.description;
            editForm.querySelector('[name="priority"]').value = button.dataset.priority;
            editForm.querySelector('[name="scheduled_date"]').value = button.dataset.scheduled;
            editForm.querySelector('[name="completion_deadline"]').value = button.dataset.deadline;
        });
    });

});
