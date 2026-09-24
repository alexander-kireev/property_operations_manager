document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.querySelector(".property-command-centre");
    if (!workspace) return;

    const tabs = [...workspace.querySelectorAll("[data-property-tab]")];
    const panels = [...workspace.querySelectorAll("[data-property-panel]")];

    function showTab(name, updateUrl = true) {
        tabs.forEach((tab) => {
            const active = tab.dataset.propertyTab === name;
            tab.classList.toggle("is-active", active);
            tab.setAttribute("aria-selected", String(active));
            tab.tabIndex = active ? 0 : -1;
        });
        panels.forEach((panel) => {
            panel.hidden = panel.dataset.propertyPanel !== name;
        });
        if (updateUrl) {
            const url = new URL(window.location.href);
            if (name === "overview") url.searchParams.delete("tab");
            else url.searchParams.set("tab", name);
            window.history.replaceState(null, "", url);
        }
    }

    workspace.addEventListener("click", (event) => {
        const tab = event.target.closest("[data-property-tab], [data-property-tab-shortcut]");
        if (tab) showTab(tab.dataset.propertyTab || tab.dataset.propertyTabShortcut);
    });

    workspace.querySelector(".property-tabs")?.addEventListener("keydown", (event) => {
        const current = tabs.indexOf(event.target);
        if (current < 0) return;
        let next;
        if (event.key === "ArrowRight") next = tabs[(current + 1) % tabs.length];
        if (event.key === "ArrowLeft") next = tabs[(current - 1 + tabs.length) % tabs.length];
        if (event.key === "Home") next = tabs[0];
        if (event.key === "End") next = tabs[tabs.length - 1];
        if (next) {
            event.preventDefault();
            showTab(next.dataset.propertyTab);
            next.focus();
        }
    });

    showTab(tabs.find((tab) => tab.getAttribute("aria-selected") === "true")?.dataset.propertyTab || "overview", false);

    const quickModal = document.getElementById("propertyQuickActionModal");
    quickModal?.addEventListener("show.bs.modal", (event) => {
        const button = event.relatedTarget;
        const verb = button.dataset.verb;
        const kind = button.dataset.kind;
        quickModal.querySelector("form").action = button.dataset.action;
        quickModal.querySelector('[name="next"]').value = button.dataset.return;
        quickModal.querySelector(".modal-title").textContent = `${verb} ${kind}?`;
        quickModal.querySelector("[data-quick-question]").textContent = `${verb} this ${kind}?`;
        quickModal.querySelector("[data-quick-kind]").textContent = kind[0].toUpperCase() + kind.slice(1);
        quickModal.querySelector("[data-quick-name]").textContent = button.dataset.name;
        quickModal.querySelector("[data-quick-submit]").textContent = `${verb} ${kind}`;
        const linkedTasks = quickModal.querySelector("[data-quick-linked]");
        linkedTasks.hidden = kind !== "issue";
        linkedTasks.querySelector("input").checked = false;
    });
});
