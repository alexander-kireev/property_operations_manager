const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/workspace-list-scroll.js"), "utf8");

function openWorkspace(storage, {
    workspace = "contacts", search = "", hash = "", query = "", mobile = false,
    listVisible = true, navigationType = "navigate", initialPageY = 0, detailId = null,
} = {}) {
    const frames = [];
    const handlers = {};
    const pathname = `/${workspace}/${detailId ? `${detailId}/` : ""}`;
    const origin = "http://localhost";
    const list = {
        scrollTop: 0,
        addEventListener: (name, callback) => { handlers[`list:${name}`] = callback; },
        getClientRects: () => listVisible ? [{}] : [],
    };
    const root = {
        dataset: { workspaceScrollRoot: workspace, navigationQuery: query, workspaceScrollPath: workspace === "properties" ? "/properties/" : undefined },
        querySelector: () => list,
        addEventListener: (name, callback) => { handlers[`root:${name}`] = callback; },
    };
    const browser = {
        location: { origin, pathname, search, hash, href: `${origin}${pathname}${search}${hash}` },
        scrollY: initialPageY,
        matchMedia: () => ({ matches: mobile }),
        performance: { getEntriesByType: () => [{ type: navigationType }] },
        scrollTo: (_x, y) => { browser.scrollY = y; },
        addEventListener: (name, callback) => { handlers[`window:${name}`] = callback; },
    };
    vm.runInNewContext(source, {
        document: {
            querySelector: () => root,
            addEventListener: (name, callback) => { handlers[`document:${name}`] = callback; },
        },
        window: browser,
        sessionStorage: {
            getItem: (key) => storage.get(key) ?? null,
            setItem: (key, value) => storage.set(key, value),
            removeItem: (key) => storage.delete(key),
        },
        URL, URLSearchParams,
        requestAnimationFrame: (callback) => { frames.push(callback); return frames.length; },
    });
    return {
        browser, list,
        flush: () => { while (frames.length) frames.shift()(); },
        pageShow: (persisted = false) => handlers["window:pageshow"]({ persisted }),
        clickLink: (href, { prevented = false } = {}) => {
            const link = { href: new URL(href, `${origin}${pathname}`).href, target: "" };
            handlers["root:click"]({
                target: { closest: () => link }, button: 0, defaultPrevented: prevented,
            });
        },
        scrollList: (position) => { list.scrollTop = position; handlers["list:scroll"](); },
        scrollPage: (position) => { browser.scrollY = position; handlers["window:scroll"](); },
        submit: (action, next = "") => handlers["document:submit"]({
            target: {
                action: new URL(action, `${origin}${pathname}`).href,
                elements: { namedItem: () => ({ value: next }) },
            }, defaultPrevented: false,
        }),
    };
}

test("row selection and refresh retain desktop list scroll", () => {
    const storage = new Map();
    const first = openWorkspace(storage);
    first.flush();
    first.scrollList(430); first.flush(); first.clickLink("?selected=7");
    const selected = openWorkspace(storage, { search: "?selected=7" });
    selected.flush();
    assert.equal(selected.list.scrollTop, 430);
    const refreshed = openWorkspace(storage, { search: "?selected=7", navigationType: "reload" });
    refreshed.flush();
    assert.equal(refreshed.list.scrollTop, 430);
});

test("fresh navbar entry with unchanged filters starts at the top on mobile and desktop", () => {
    for (const mobile of [true, false]) {
        const storage = new Map();
        const first = openWorkspace(storage, { mobile });
        first.flush();
        if (mobile) first.scrollPage(620); else first.scrollList(430);
        first.flush();
        const fresh = openWorkspace(storage, { mobile, initialPageY: 620 });
        fresh.flush();
        assert.equal(mobile ? fresh.browser.scrollY : fresh.list.scrollTop, 0);
        assert.equal(storage.size, 0);
    }
});

test("changing filters discards the old position and navigation marker", () => {
    const storage = new Map();
    const first = openWorkspace(storage);
    first.flush();
    first.scrollList(430); first.flush(); first.clickLink("?search=roof");
    const filtered = openWorkspace(storage, { search: "?search=roof", query: "search=roof" });
    filtered.flush();
    assert.equal(filtered.list.scrollTop, 0);
    assert.equal(storage.size, 0);
});

test("mobile detail starts at top and Back restores its list", () => {
    for (const workspace of ["contacts", "tasks", "issues"]) {
        const storage = new Map();
        const first = openWorkspace(storage, { workspace, mobile: true });
        first.flush();
        first.scrollPage(620); first.flush(); first.clickLink("?selected=7");
        const selected = openWorkspace(storage, {
            workspace, search: "?selected=7", mobile: true, listVisible: false, initialPageY: 620,
        });
        selected.flush(); selected.pageShow(); selected.flush();
        assert.equal(selected.browser.scrollY, 0, workspace);
        selected.clickLink(`/${workspace}/`);
        const back = openWorkspace(storage, { workspace, mobile: true });
        back.flush();
        assert.equal(back.browser.scrollY, 620, workspace);
    }
});

test("direct mobile detail starts at the top even without a saved list", () => {
    const selected = openWorkspace(new Map(), {
        search: "?selected=7", mobile: true, listVisible: false, initialPageY: 500,
    });
    selected.flush();
    assert.equal(selected.browser.scrollY, 0);
});

test("browser Back restores a list without an internal-link marker", () => {
    const storage = new Map();
    const first = openWorkspace(storage, { mobile: true });
    first.flush();
    first.scrollPage(510); first.flush();
    const back = openWorkspace(storage, { mobile: true, navigationType: "back_forward" });
    back.flush();
    assert.equal(back.browser.scrollY, 510);
});

test("a bfcache return keeps the browser-restored position", () => {
    const page = openWorkspace(new Map(), { mobile: true });
    page.flush(); page.browser.scrollY = 475; page.pageShow(true); page.flush();
    assert.equal(page.browser.scrollY, 475);
});

test("expanded mobile Events keeps tracking its visible list and respects its row anchor", () => {
    const storage = new Map();
    const first = openWorkspace(storage, { workspace: "events", mobile: true });
    first.flush();
    first.scrollPage(300); first.flush(); first.clickLink("?selected=7&tab=details");
    const selected = openWorkspace(storage, {
        workspace: "events", search: "?selected=7&tab=details", hash: "#eventRow7",
        mobile: true, initialPageY: 720,
    });
    selected.flush();
    assert.equal(selected.browser.scrollY, 720);
    selected.scrollPage(820); selected.flush();
    assert.equal(JSON.parse(storage.get("pom:workspace-list-scroll:events")).pageScrollY, 820);
});

test("same-workspace form redirect keeps the list position", () => {
    const storage = new Map();
    const first = openWorkspace(storage);
    first.flush();
    first.scrollList(390); first.flush(); first.submit("/contacts/7/edit/");
    const selected = openWorkspace(storage, { search: "?selected=7" });
    selected.flush();
    assert.equal(selected.list.scrollTop, 390);
});

test("property list and detail URLs share desktop and mobile list position", () => {
    for (const mobile of [false, true]) {
        const storage = new Map();
        const first = openWorkspace(storage, { workspace: "properties", mobile });
        first.flush();
        if (mobile) first.scrollPage(520); else first.scrollList(380);
        first.flush();
        first.clickLink("/properties/7/");

        const detail = openWorkspace(storage, {
            workspace: "properties", detailId: 7, mobile, listVisible: !mobile,
            initialPageY: mobile ? 520 : 0,
        });
        detail.flush();
        assert.equal(mobile ? detail.browser.scrollY : detail.list.scrollTop, mobile ? 0 : 380);
        detail.clickLink("/properties/");

        const back = openWorkspace(storage, { workspace: "properties", mobile });
        back.flush();
        assert.equal(mobile ? back.browser.scrollY : back.list.scrollTop, mobile ? 520 : 380);
    }
});

test("property quick action keeps list position through another workspace POST", () => {
    const storage = new Map();
    const detail = openWorkspace(storage, { workspace: "properties", detailId: 7 });
    detail.flush();
    detail.scrollList(310); detail.flush();
    detail.submit("/tasks/12/complete/", "/properties/7/?tab=work");

    const returned = openWorkspace(storage, { workspace: "properties", detailId: 7, search: "?tab=work" });
    returned.flush();
    assert.equal(returned.list.scrollTop, 310);
});
