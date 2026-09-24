document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.querySelector(".property-command-centre");
    if (!workspace) return;

    const descriptionPreview = workspace.querySelector("[data-property-description-preview]");
    const descriptionOpen = workspace.querySelector("[data-property-description-open]");

    function updateDescriptionPreview() {
        if (!descriptionPreview || !descriptionOpen || descriptionPreview.offsetWidth === 0) return;
        descriptionPreview.classList.add("is-clamped");
        const overflowed = descriptionPreview.scrollHeight > descriptionPreview.clientHeight + 1;
        if (!overflowed) descriptionPreview.classList.remove("is-clamped");
        descriptionOpen.hidden = !overflowed;
    }

    updateDescriptionPreview();
    window.addEventListener("resize", updateDescriptionPreview);

});
