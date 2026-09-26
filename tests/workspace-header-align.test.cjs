const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = readFileSync(path.join(__dirname, "../static/js/workspace-header-align.js"), "utf8");

function openWorkspace({ width, minimumWidth, listHeight, detailHeight }) {
    const frames = [];
    const handlers = {};
    const header = (naturalHeight) => ({
        style: { minHeight: "" },
        // The content measurement excludes the 1px separator border.
        scrollHeight: naturalHeight - 1,
        getBoundingClientRect() {
            return { height: Math.max(naturalHeight, Number.parseFloat(this.style.minHeight) || 0) };
        },
    });
    const list = header(listHeight);
    const detail = header(detailHeight);
    const workspace = {
        dataset: { alignFrom: String(minimumWidth) },
        querySelector: (selector) => selector === "[data-list-header]" ? list : detail,
    };
    const browser = {
        innerWidth: width,
        requestAnimationFrame(callback) { frames.push(callback); return frames.length; },
        addEventListener(name, callback) { handlers[name] = callback; },
    };
    vm.runInNewContext(source, {
        document: {
            addEventListener: (_name, callback) => { handlers.ready = callback; },
            querySelectorAll: () => [workspace],
            fonts: { ready: { then: () => {} } },
        },
        window: browser,
    });
    handlers.ready();
    const flush = () => { while (frames.length) frames.shift()(); };
    return { list, detail, browser, flush, resize: () => handlers.resize() };
}

for (const [name, minimumWidth] of [["Properties", 992], ["Contacts", 992]]) {
    for (const width of [1280, minimumWidth]) {
        test(`${name} separators align using border-box height at ${width}px viewport width`, () => {
            const page = openWorkspace({ width, minimumWidth, listHeight: 120, detailHeight: 225.4 });
            page.flush();
            assert.equal(page.list.getBoundingClientRect().height, 226);
            assert.equal(page.detail.getBoundingClientRect().height, 226);
        });
    }

    test(`${name} alignment clears below the single-column breakpoint`, () => {
        const page = openWorkspace({ width: minimumWidth, minimumWidth, listHeight: 120, detailHeight: 225.4 });
        page.flush();
        page.browser.innerWidth = minimumWidth - 1;
        page.resize();
        page.flush();
        assert.equal(page.list.style.minHeight, "");
        assert.equal(page.detail.style.minHeight, "");
    });
}
