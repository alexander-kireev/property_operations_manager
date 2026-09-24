// Restore a workspace list on refresh, browser Back, and navigation within the
// workspace, but not when arriving afresh from another part of the app.
(() => {
    const root = document.querySelector("[data-workspace-scroll-root]");
    if (!root) return;

    const list = root.querySelector("[data-workspace-scroll-list]");
    const query = new URLSearchParams(root.dataset.navigationQuery || "");
    const workspacePath = root.dataset.workspaceScrollPath || window.location.pathname;
    const key = `${workspacePath}?${query.toString()}`;
    const storageKey = `pom:workspace-list-scroll:${root.dataset.workspaceScrollRoot}`;
    const intentKey = `${storageKey}:navigation-intent`;
    const usesPageScroll = () => window.matchMedia("(max-width: 767.98px)").matches;
    const navigationType = window.performance?.getEntriesByType?.("navigation")?.[0]?.type || "navigate";

    const read = () => {
        try {
            return JSON.parse(sessionStorage.getItem(storageKey));
        } catch {
            return null;
        }
    };
    const write = (position) => {
        try {
            sessionStorage.setItem(storageKey, JSON.stringify(position));
        } catch {
            // Storage may be unavailable; normal link navigation still works.
        }
    };
    const clear = () => {
        try {
            sessionStorage.removeItem(storageKey);
        } catch {
            // Nothing to clear if storage is unavailable.
        }
    };
    const markInternalNavigation = () => {
        try {
            sessionStorage.setItem(intentKey, key);
        } catch {
            // Navigation still works without session storage.
        }
    };
    const consumeInternalNavigation = () => {
        try {
            const intendedKey = sessionStorage.getItem(intentKey);
            sessionStorage.removeItem(intentKey);
            return intendedKey === key;
        } catch {
            return false;
        }
    };

    const saved = read();
    const internalNavigation = consumeInternalNavigation();
    if (saved && saved.key !== key) clear();
    if (!list) return;
    const shouldRestore = saved?.key === key && (
        internalNavigation || navigationType === "reload" || navigationType === "back_forward"
    );
    if (!shouldRestore && navigationType === "navigate") clear();

    const hiddenMobileDetail = () => usesPageScroll() && !list.getClientRects().length;
    const restore = () => {
        if (hiddenMobileDetail()) {
            window.scrollTo(0, 0);
        } else if (usesPageScroll()) {
            // A date or selected-row anchor is more specific than saved page scroll.
            if (!window.location.hash) window.scrollTo(0, shouldRestore ? saved.pageScrollY || 0 : 0);
        } else if (shouldRestore) {
            list.scrollTop = saved.listScrollTop || 0;
        }
    };
    requestAnimationFrame(restore);
    window.addEventListener("pageshow", (event) => {
        // A bfcache return already carries the browser's exact scroll position.
        if (!event.persisted) requestAnimationFrame(restore);
    });

    const capturePosition = () => {
        const previous = read();
        const listVisible = Boolean(list.getClientRects().length);
        write({
            key,
            listScrollTop: listVisible ? list.scrollTop : previous?.key === key ? previous.listScrollTop : 0,
            pageScrollY: listVisible ? window.scrollY : previous?.key === key ? previous.pageScrollY : 0,
        });
        markInternalNavigation();
    };

    let scrollFrame = null;
    list.addEventListener("scroll", () => {
        if (usesPageScroll() || scrollFrame !== null) return;
        scrollFrame = requestAnimationFrame(() => {
            scrollFrame = null;
            const previous = read();
            write({
                key,
                listScrollTop: list.scrollTop,
                pageScrollY: previous?.key === key ? previous.pageScrollY : 0,
            });
        });
    }, { passive: true });

    let pageFrame = null;
    window.addEventListener("scroll", () => {
        if (!usesPageScroll() || !list.getClientRects().length || pageFrame !== null) return;
        pageFrame = requestAnimationFrame(() => {
            pageFrame = null;
            const previous = read();
            write({
                key,
                listScrollTop: previous?.key === key ? previous.listScrollTop : 0,
                pageScrollY: window.scrollY,
            });
        });
    }, { passive: true });

    root.addEventListener("click", (event) => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const link = event.target.closest("a[href]");
        if (!link || (link.target && link.target !== "_self")) return;
        const target = new URL(link.href);
        if (target.origin !== window.location.origin || !target.pathname.startsWith(workspacePath)) return;
        if (target.search === window.location.search && target.hash) return;
        capturePosition();
    });

    document.addEventListener("submit", (event) => {
        const form = event.target;
        if (event.defaultPrevented || !form.action) return;
        const target = new URL(form.action);
        const returnUrl = form.elements?.namedItem("next")?.value;
        let returningToWorkspace = false;
        if (returnUrl) {
            try {
                const destination = new URL(returnUrl, window.location.href);
                returningToWorkspace = destination.origin === window.location.origin
                    && destination.pathname.startsWith(workspacePath);
            } catch {
                // An invalid return URL does not affect form submission.
            }
        }
        if ((target.origin === window.location.origin && target.pathname.startsWith(workspacePath)) || returningToWorkspace) {
            capturePosition();
        }
    });
})();
