document.addEventListener("DOMContentLoaded", () => {
    const dashboard = document.getElementById("dashboard");
    if (!dashboard) return;

    const get = (id) => document.getElementById(id);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character]);
    const parseDate = (value) => new Date(`${value}T12:00:00Z`);
    const isoDate = (value) => value.toISOString().slice(0, 10);
    const prettyDate = (value) => parseDate(value).toLocaleDateString("en-GB", {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"});
    const longDate = (value) => parseDate(value).toLocaleDateString("en-GB", {weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC"});
    const mondayOf = (value) => {
        const day = parseDate(value);
        day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
        return day;
    };
    const cookie = document.cookie.split("; ").find((part) => part.startsWith("csrftoken="));
    const csrfToken = cookie ? decodeURIComponent(cookie.slice(10)) : "";
    const filters = {
        task: [["all", "All active"], ["unscheduled", "Unscheduled"], ["scheduled", "Scheduled"], ["today", "Today"], ["urgent", "High / urgent"]],
        issue: [["all", "All open"], ["urgent", "High / urgent"], ["soon", "Resolve soon"]],
        event: [["all", "All scheduled"], ["week", "This week"], ["month", "This month"]],
    };
    let data = {records: {task: [], issue: [], event: []}, notes: [], properties: [], issues: [], today: ""};
    let kind = "task";
    let filter = "unscheduled";
    let selected = "";
    let dayTab = "tasks";
    let rightView = "day";
    let dayScroll = 0;
    let notesScroll = 0;
    let month = null;
    let shown = 40;
    let expanded = null;
    let editingNote = null;
    let recordTarget = null;
    let confirmTarget = null;
    let dragged = null;
    let toastTimer = null;
    let workPending = false;
    let confirmPending = false;

    function hideToast() {
        const toast = get("dashboardToast");
        if (toast.hidden) return;
        clearTimeout(toastTimer);
        toast.classList.add("leaving");
        setTimeout(() => { if (toast.classList.contains("leaving")) toast.hidden = true; }, 180);
    }
    function message(title, {detail = "", error = false} = {}) {
        const toast = get("dashboardToast");
        clearTimeout(toastTimer);
        toast.classList.remove("leaving");
        toast.classList.toggle("error", error);
        toast.setAttribute("role", error ? "alert" : "status");
        toast.setAttribute("aria-live", error ? "assertive" : "polite");
        get("dashboardToastIcon").textContent = error ? "!" : "✓";
        get("dashboardToastTitle").textContent = title;
        get("dashboardToastDetail").textContent = detail;
        toast.hidden = false;
        if (!error) toastTimer = setTimeout(hideToast, 4200);
    }
    function findRecord(type, id) { return data.records[type].find((item) => item.id === Number(id)); }
    function recordError(body) {
        if (body.error) return body.error;
        if (body.errors) return Object.entries(body.errors).map(([field, values]) => `${field}: ${values.join(", ")}`).join(" · ");
        return "Unable to save. Please try again.";
    }
    async function send(fields) {
        const body = new URLSearchParams(fields);
        let response;
        try {
            response = await fetch(dashboard.dataset.actionUrl, {
                method: "POST", headers: {"X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded"},
                credentials: "same-origin", body,
            });
        } catch {
            throw new Error("Could not connect. Check your connection and try again.");
        }
        const result = await response.json().catch(() => null);
        if (!result) throw new Error("The server could not process that request. Please try again.");
        if (!response.ok) {
            const error = new Error(recordError(result));
            error.fieldErrors = result.errors || null;
            throw error;
        }
        return result;
    }
    async function load({keepScroll = true} = {}) {
        const queueScroll = keepScroll ? get("workList").scrollTop : 0;
        const dayScroll = keepScroll ? get("dayList").scrollTop : 0;
        const response = await fetch(dashboard.dataset.dataUrl, {credentials: "same-origin"});
        if (!response.ok) { message("Dashboard could not load.", {error: true}); return; }
        data = await response.json();
        if (!selected) selected = data.today;
        if (!month) month = parseDate(`${selected.slice(0, 7)}-01`);
        render();
        get("workList").scrollTop = queueScroll;
        get("dayList").scrollTop = dayScroll;
    }

    function visibleRecords() {
        const search = get("workSearch").value.trim().toLowerCase();
        const weekEnd = new Date(mondayOf(data.today));
        weekEnd.setUTCDate(weekEnd.getUTCDate() + 6);
        return data.records[kind].filter((item) => {
            if (search && !`${item.title} ${item.description} ${item.property}`.toLowerCase().includes(search)) return false;
            if (kind === "task") {
                if (filter === "unscheduled") return !item.date;
                if (filter === "scheduled") return !!item.date;
                if (filter === "today") return item.date === data.today;
                if (filter === "urgent") return ["High", "Urgent"].includes(item.priority);
            } else if (kind === "issue") {
                if (filter === "urgent") return ["High", "Urgent"].includes(item.priority);
                if (filter === "soon") return item.due && item.due <= isoDate(weekEnd);
            } else {
                if (filter === "week") return item.date >= isoDate(mondayOf(data.today)) && item.date <= isoDate(weekEnd);
                if (filter === "month") return item.date.startsWith(data.today.slice(0, 7));
            }
            return true;
        });
    }
    function badge(item) {
        if (item.priority) return `<span class="work-pill work-pill--priority-${item.priority_id}">${escapeHtml(item.priority)}</span>`;
        return "";
    }
    function recordMeta(item) {
        if (item.kind === "task") return `${item.property || (item.issue_id ? "Linked issue" : "Standalone")} · ${item.date ? `Scheduled ${prettyDate(item.date)}` : "Unscheduled"}${item.due ? ` · Due ${prettyDate(item.due)}` : ""}`;
        if (item.kind === "issue") return `${item.property || "No property"}${item.due ? ` · Resolve by ${prettyDate(item.due)}` : ""}`;
        return `${item.property || "No property"} · ${prettyDate(item.date)}${item.all_day ? " · All day" : item.start_time ? ` · ${item.start_time}${item.end_time ? `–${item.end_time}` : ""}` : ""}`;
    }
    function recordRow(item, area) {
        const key = `${area}-${item.kind}-${item.id}`;
        const isExpanded = expanded === key;
        const canDrag = item.kind === "task" || item.kind === "event" || area === "due" && item.kind === "issue";
        const finish = {task: "Complete", issue: "Resolve", event: "Mark occurred"}[item.kind];
        const fullUrl = `${dashboard.dataset[`${item.kind}Url`]}?selected=${item.id}&open=detail`;
        const chevron = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m5 9 7 7 7-7"/></svg>';
        const typeCue = area === "due" ? `<span class="dashboard-type-cue"><span aria-hidden="true">${{task: "▤", issue: "◇"}[item.kind]}</span> ${item.kind === "task" ? "Task" : "Issue"}</span>` : "";
        const menuId = `dashboard-actions-${key}`;
        const actions = `<div class="dashboard-row-actions">
            <button type="button" class="dashboard-action-primary" data-action="finish">${finish}</button>
            <button type="button" data-action="edit">Edit</button>
            ${item.kind === "event" ? '<button type="button" class="dashboard-optional-action" data-action="cancel">Cancel</button>' : ""}
            <button type="button" class="dashboard-optional-action dashboard-action-danger" data-action="delete">Delete</button>
            <a class="dashboard-optional-action" href="${escapeHtml(fullUrl)}">Open record</a>
            <button type="button" class="dashboard-more-button" data-action="more" aria-label="More actions for ${escapeHtml(item.title)}" aria-controls="${menuId}" aria-expanded="false">⋮</button>
            <div class="dashboard-row-menu" id="${menuId}" popover="auto">
                ${item.kind === "event" ? '<button type="button" data-action="cancel">Cancel event</button>' : ""}
                <a href="${escapeHtml(fullUrl)}">Open record</a>
                <button type="button" class="dashboard-action-danger" data-action="delete">Delete</button>
            </div>
        </div>`;
        return `<article class="${area === "queue" ? "dashboard-work-row" : "dashboard-day-row"}" data-area="${area}" data-kind="${item.kind}" data-id="${item.id}" ${canDrag ? 'draggable="true"' : ""} ${area === "due" && item.due ? `data-scheduled-date="${item.due}"` : item.date ? `data-scheduled-date="${item.date}"` : ""}>
            <button class="dashboard-row-toggle" type="button" aria-expanded="${isExpanded}" aria-label="${isExpanded ? "Collapse" : "Expand"} ${escapeHtml(item.title)}">
                <span class="dashboard-row-main"><strong>${escapeHtml(item.title)}</strong><small>${typeCue}${escapeHtml(recordMeta(item))}</small></span>
                <span class="dashboard-row-side">${badge(item)}<span class="dashboard-row-chevron">${chevron}</span></span>
            </button>
            <div class="dashboard-row-detail" ${isExpanded ? "" : "hidden"}>
                ${item.description ? `<p>${escapeHtml(item.description)}</p>` : `<p class="text-body-secondary">No description.</p>`}
                <div class="dashboard-row-facts"><span>${escapeHtml(item.property || (item.issue_id ? "Linked issue" : "No property"))}</span>${item.date ? `<span>${item.kind === "event" ? "Date" : "Scheduled"} ${prettyDate(item.date)}</span>` : item.kind === "task" ? "<span>Unscheduled</span>" : ""}${item.due ? `<span>${item.kind === "issue" ? "Resolve by" : "Due"} ${prettyDate(item.due)}</span>` : ""}${item.kind === "event" && item.start_time ? `<span>${escapeHtml(item.start_time)}${item.end_time ? `–${escapeHtml(item.end_time)}` : ""}</span>` : ""}</div>
                ${actions}
            </div>
        </article>`;
    }
    function renderQueue() {
        const items = visibleRecords();
        for (const type of ["task", "issue", "event"]) {
            const count = type === kind ? items.length : data.records[type].length;
            get("dashboard").querySelector(`[data-count="${type}"]`).textContent = count;
        }
        document.querySelectorAll("[data-kind][role=tab]").forEach((button) => button.setAttribute("aria-selected", String(button.dataset.kind === kind)));
        get("workSearch").placeholder = `Search ${kind}s`;
        const options = get("workFilter");
        options.innerHTML = filters[kind].map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
        options.value = filter;
        window.SearchableSelect?.refresh(options);
        get("workList").innerHTML = items.length ? items.slice(0, shown).map((item) => recordRow(item, "queue")).join("") : '<p class="dashboard-empty">No records match this search and filter.</p>';
    }
    function appendMore() {
        const list = get("workList");
        if (list.scrollTop + list.clientHeight < list.scrollHeight - 100) return;
        const items = visibleRecords();
        if (shown >= items.length) return;
        const previous = shown;
        shown += 40;
        list.insertAdjacentHTML("beforeend", items.slice(previous, shown).map((item) => recordRow(item, "queue")).join(""));
    }
    function calendarStart() {
        const start = new Date(month);
        start.setUTCDate(1 - ((start.getUTCDay() + 6) % 7));
        return start;
    }
    function countByDate(items, field) {
        const counts = new Map();
        for (const item of items) {
            if (item[field]) counts.set(item[field], (counts.get(item[field]) || 0) + 1);
        }
        return counts;
    }
    function renderCalendar() {
        const year = month.getUTCFullYear();
        const monthNumber = month.getUTCMonth();
        const monthSelect = get("calendarMonth");
        const yearSelect = get("calendarYear");
        if (!monthSelect.options.length) monthSelect.innerHTML = Array.from({length: 12}, (_, index) => `<option value="${index}">${new Date(Date.UTC(2026, index, 1)).toLocaleDateString("en-GB", {month: "long", timeZone: "UTC"})}</option>`).join("");
        yearSelect.innerHTML = Array.from({length: 21}, (_, index) => `<option value="${year - 10 + index}">${year - 10 + index}</option>`).join("");
        monthSelect.value = String(monthNumber);
        yearSelect.value = String(year);
        window.SearchableSelect?.refresh(monthSelect);
        window.SearchableSelect?.refresh(yearSelect);
        const start = calendarStart();
        const lastDay = new Date(Date.UTC(year, monthNumber + 1, 0));
        const weeks = Math.ceil((lastDay.getUTCDate() + ((month.getUTCDay() + 6) % 7)) / 7);
        const scheduledTasks = countByDate(data.records.task, "date");
        const scheduledEvents = countByDate(data.records.event, "date");
        const taskDeadlines = countByDate(data.records.task, "due");
        const issueDeadlines = countByDate(data.records.issue, "due");
        const cells = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => `<span class="dashboard-weekday">${day}</span>`);
        for (let index = 0; index < weeks * 7; index++) {
            const date = new Date(start);
            date.setUTCDate(start.getUTCDate() + index);
            const value = isoDate(date);
            const tasks = scheduledTasks.get(value) || 0;
            const events = scheduledEvents.get(value) || 0;
            const due = (taskDeadlines.get(value) || 0) + (issueDeadlines.get(value) || 0);
            cells.push(`<button type="button" class="dashboard-day ${date.getUTCMonth() !== monthNumber ? "other" : ""} ${value === selected ? "selected" : ""}" data-day="${value}" aria-label="${longDate(value)}, ${tasks} scheduled task${tasks === 1 ? "" : "s"}, ${events} event${events === 1 ? "" : "s"}, ${due} deadline${due === 1 ? "" : "s"}"><strong>${date.getUTCDate()}</strong>${tasks ? `<span class="dashboard-day-count">▤ ${tasks}<span class="dashboard-count-label"> task${tasks === 1 ? "" : "s"}</span></span>` : ""}${events ? `<span class="dashboard-event-count">○ ${events}<span class="dashboard-count-label"> event${events === 1 ? "" : "s"}</span></span>` : ""}${due ? `<span class="dashboard-due-count">◆ ${due}<span class="dashboard-count-label"> due</span></span>` : ""}</button>`);
        }
        const grid = get("calendarGrid");
        grid.innerHTML = cells.join("");
    }
    function renderDay() {
        const selectedDate = parseDate(selected);
        get("selectedDayNumber").textContent = selectedDate.getUTCDate();
        get("selectedDayMonth").textContent = selectedDate.toLocaleDateString("en-GB", {month: "short", timeZone: "UTC"}).toUpperCase();
        get("selectedDayHeading").textContent = selectedDate.toLocaleDateString("en-GB", {weekday: "long", timeZone: "UTC"});
        get("selectedDayHeading").setAttribute("aria-label", longDate(selected));
        const tasks = data.records.task.filter((item) => item.date === selected);
        const events = data.records.event.filter((item) => item.date === selected);
        const dueTasks = data.records.task.filter((item) => item.due === selected);
        const dueIssues = data.records.issue.filter((item) => item.due === selected);
        const due = [...dueTasks, ...dueIssues];
        get("selectedDayCount").textContent = `${tasks.length} task${tasks.length === 1 ? "" : "s"} · ${events.length} event${events.length === 1 ? "" : "s"} · ${due.length} deadline${due.length === 1 ? "" : "s"}`;
        const groups = {tasks, deadlines: due, events};
        for (const tab of get("dashboard").querySelectorAll("[data-day-tab]")) {
            tab.setAttribute("aria-selected", String(tab.dataset.dayTab === dayTab));
            get("dashboard").querySelector(`[data-day-count="${tab.dataset.dayTab}"]`).textContent = groups[tab.dataset.dayTab].length;
        }
        get("dayList").setAttribute("aria-labelledby", {tasks: "dayTabTasks", deadlines: "dayTabDeadlines", events: "dayTabEvents"}[dayTab]);
        const items = groups[dayTab];
        const area = dayTab === "deadlines" ? "due" : "day";
        const empty = {tasks: "No tasks scheduled for this day.", deadlines: "No task or issue deadlines for this day.", events: "No events scheduled for this day."};
        get("dayList").innerHTML = items.length ? items.map((item) => recordRow(item, area)).join("") : `<p class="dashboard-empty">${empty[dayTab]}</p>`;
    }
    function renderNotes() {
        get("notesCount").textContent = data.notes.length;
        get("notesList").innerHTML = data.notes.length ? data.notes.map((note) => `<article class="dashboard-note" data-note="${note.id}">
            ${editingNote === note.id ? `<textarea maxlength="250" aria-label="Edit note">${escapeHtml(note.content)}</textarea><div class="dashboard-note-edit-actions"><button type="button" data-note-action="cancel">Cancel</button><button type="button" data-note-action="save">Save</button></div>` : `<p>${escapeHtml(note.content)}</p><div class="dashboard-note-actions"><button type="button" data-note-action="edit" aria-label="Edit note"><svg aria-hidden="true" viewBox="0 0 16 16" focusable="false"><path d="M12.9 1.7a1.5 1.5 0 0 1 2.1 2.1l-9.5 9.5-3.1.8.8-3.1 9.7-9.3Zm-8.8 9.9-.3 1.1 1.1-.3 8.2-8.2-.8-.8-8.2 8.2Z"/></svg></button><button type="button" class="dashboard-note-delete" data-note-action="delete" aria-label="Delete note"><svg aria-hidden="true" viewBox="0 0 16 16" focusable="false"><path d="M3.3 2.3 8 7l4.7-4.7 1 1L9 8l4.7 4.7-1 1L8 9l-4.7 4.7-1-1L7 8 2.3 3.3l1-1Z"/></svg></button></div><small>${escapeHtml(note.created)}</small>`}
        </article>`).join("") : '<p class="dashboard-empty">No notes yet.</p>';
    }
    function render() { renderQueue(); renderCalendar(); renderDay(); renderNotes(); }
    function showRightView(view) {
        if (rightView !== view) {
            if (rightView === "day") dayScroll = get("dayList").scrollTop;
            else notesScroll = get("notesList").scrollTop;
        }
        rightView = view;
        get("dayView").hidden = view !== "day";
        get("notesView").hidden = view !== "notes";
        get("dayViewToggle").setAttribute("aria-selected", String(view === "day"));
        get("notesViewToggle").setAttribute("aria-selected", String(view === "notes"));
        if (view === "day") get("dayList").scrollTop = dayScroll;
        else get("notesList").scrollTop = notesScroll;
    }
    function selectDay(value) {
        const changed = selected !== value;
        selected = value;
        month = parseDate(`${value.slice(0, 7)}-01`);
        renderCalendar(); renderDay();
        showRightView("day");
        if (changed) { dayScroll = 0; get("dayList").scrollTop = 0; }
    }

    function formField(name, label, value = "", type = "text") {
        return `<label>${label}<input class="form-control" name="${name}" type="${type}" value="${escapeHtml(value)}" ${name === "title" ? 'maxlength="100" required' : ""}><span class="dashboard-field-error" data-error-for="${name}" role="alert"></span></label>`;
    }
    function selectField(name, label, choices, selectedValue) {
        return `<label>${label}<select class="form-select" name="${name}">${choices.map(([value, text]) => `<option value="${escapeHtml(value)}" ${String(value) === String(selectedValue ?? "") ? "selected" : ""}>${escapeHtml(text)}</option>`).join("")}</select><span class="dashboard-field-error" data-error-for="${name}" role="alert"></span></label>`;
    }
    function workFields(type, item) {
        const properties = [["", "No property"], ...data.properties.map((property) => [property.id, property.name])];
        const priorities = [[1, "Low"], [2, "Medium"], [3, "High"], [4, "Urgent"]];
        let html = formField("title", "Title", item?.title);
        html += `<label>Description<textarea class="form-control" name="description" maxlength="1000">${escapeHtml(item?.description)}</textarea><span class="dashboard-field-error" data-error-for="description" role="alert"></span></label>`;
        if (type === "task") {
            const relationship = item?.issue_id ? "issue" : item?.property_id ? "property" : "standalone";
            html += selectField("relationship_type", "Related to", [["standalone", "Standalone"], ["property", "Property"], ["issue", "Issue"]], relationship);
            html += `<div class="dashboard-relation-placeholder" data-relation="standalone"><span>Related record</span><span class="dashboard-unlinked-field">No linked record</span></div>`;
            html += `<div data-relation="property">${selectField("property", "Property", properties, item?.property_id)}</div>`;
            html += `<div data-relation="issue">${selectField("issue", "Issue", [["", "No issue"], ...data.issues.map((issue) => [issue.id, issue.title])], item?.issue_id)}</div>`;
            html += selectField("priority", "Priority", priorities, item?.priority_id || 1);
            html += formField("scheduled_date", "Scheduled date", item?.date, "date");
            html += formField("completion_deadline", "Completion deadline", item?.due, "date");
        } else if (type === "issue") {
            html += selectField("property", "Property", properties, item?.property_id);
            html += selectField("priority", "Priority", priorities, item?.priority_id || 1);
            html += formField("resolution_deadline", "Resolve by", item?.due, "date");
        } else {
            html += selectField("property", "Property", properties, item?.property_id);
            html += formField("scheduled_date", "Date", item?.date || selected, "date");
            html += `<label><input name="all_day" type="checkbox" ${item?.all_day ?? true ? "checked" : ""}> All day</label>`;
            html += `<div data-time-field>${formField("start_time", "Start time (HH:MM)", item?.start_time)}</div>`;
            html += `<div data-time-field>${formField("end_time", "End time (HH:MM)", item?.end_time)}</div>`;
            html += `<label><input name="user_participation_required" type="checkbox" ${item?.user_participation_required ? "checked" : ""}> My participation is required</label>`;
            html += `<label><input name="user_presence_required" type="checkbox" ${item?.user_presence_required ? "checked" : ""}> My physical presence is required</label>`;
        }
        return html;
    }
    function openWork(type, id = null, proposedDate = null) {
        const item = id ? findRecord(type, id) : null;
        recordTarget = {type, id};
        get("workDialogHeading").textContent = `${id ? "Edit" : "Add"} ${type}`;
        window.SearchableSelect?.destroyWithin(get("workFormFields"));
        get("workFormFields").innerHTML = workFields(type, item);
        window.SearchableSelect?.init(get("workFormFields"));
        if (proposedDate) get("workForm").elements.namedItem("scheduled_date").value = proposedDate;
        get("workFormErrors").textContent = "";
        updateRelationshipFields();
        updateEventTimeFields();
        get("workDialog").showModal();
        get("workForm").elements.namedItem("title").focus();
    }
    function showWorkErrors(error) {
        const errors = error.fieldErrors;
        if (!errors) { get("workFormErrors").textContent = error.message; return; }
        const summary = [...(errors.__all__ || [])];
        let firstInvalid = null;
        for (const [name, messages] of Object.entries(errors)) {
            if (name === "__all__") continue;
            const field = get("workForm").elements.namedItem(name);
            const slot = [...get("workFormFields").querySelectorAll("[data-error-for]")].find((element) => element.dataset.errorFor === name);
            if (!field || !slot || field.closest("[hidden]")) { summary.push(...messages); continue; }
            slot.textContent = messages.join(" ");
            slot.id = `workError_${name}`;
            field.setAttribute("aria-invalid", "true");
            field.setAttribute("aria-describedby", slot.id);
            field.classList.add("is-invalid");
            const trigger = field.closest(".app-select")?.querySelector(".app-select-trigger");
            if (trigger) { trigger.setAttribute("aria-invalid", "true"); trigger.setAttribute("aria-describedby", slot.id); }
            firstInvalid ||= field;
        }
        get("workFormErrors").textContent = summary.join(" ");
        if (firstInvalid) (firstInvalid.closest(".app-select")?.querySelector(".app-select-trigger") || firstInvalid).focus();
    }
    function clearWorkErrors() {
        get("workFormErrors").textContent = "";
        get("workFormFields").querySelectorAll("[name]").forEach(clearFieldError);
    }
    function updateRelationshipFields() {
        const relation = get("workForm").elements.namedItem("relationship_type")?.value;
        get("workForm").querySelectorAll("[data-relation]").forEach((section) => {
            section.hidden = section.dataset.relation !== relation;
        });
    }
    function updateEventTimeFields() {
        const allDay = get("workForm").elements.namedItem("all_day");
        get("workForm").querySelectorAll("[data-time-field]").forEach((section) => {
            section.hidden = !!allDay?.checked;
            if (allDay?.checked) section.querySelector("input").value = "";
        });
    }
    function openConfirm(type, id, action) {
        confirmTarget = {type, id, action};
        const item = findRecord(type, id);
        const heading = action === "delete" ? `Delete ${type}?` : action === "cancel" ? "Cancel event?" : {task: "Complete task?", issue: "Resolve issue?", event: "Mark event occurred?"}[type];
        get("confirmHeading").textContent = heading;
        const verb = action === "delete" ? "Delete" : action === "cancel" ? "Cancel" : {task: "Complete", issue: "Resolve", event: "Mark occurred"}[type];
        get("confirmText").textContent = `${verb} “${item.title}”?`;
        get("confirmError").textContent = "";
        get("confirmDialog").showModal();
    }
    async function changeDate(type, id, date, field = "date") {
        const item = findRecord(type, id);
        try {
            await send({action: field, kind: type, id, date});
            await load();
            const label = {task: "Task", issue: "Issue", event: "Event"}[type];
            const verb = field === "deadline" ? "deadline moved" : type === "task" && !item.date ? "scheduled" : "rescheduled";
            message(`${label} ${verb}.`, {detail: prettyDate(date)});
            return {ok: true};
        } catch (error) { message(error.message, {error: true}); return {ok: false, error: error.message}; }
    }
    function moveDraggedTo(targetDate, item) {
        const record = findRecord(item.type, item.id);
        if (!record) return;
        if (item.type === "event" && !record.all_day) {
            openWork("event", item.id, targetDate);
            return;
        }
        changeDate(item.type, item.id, targetDate, item.field);
    }
    function closeActionMenus() {
        document.querySelectorAll(".dashboard-row-menu:popover-open").forEach((menu) => menu.hidePopover());
    }
    function openActionMenu(button) {
        const menu = document.getElementById(button.getAttribute("aria-controls"));
        if (menu.matches(":popover-open")) { menu.hidePopover(); return; }
        closeActionMenus();
        menu.showPopover();
        const trigger = button.getBoundingClientRect();
        const width = menu.offsetWidth, height = menu.offsetHeight;
        menu.style.left = `${Math.max(8, Math.min(trigger.right - width, window.innerWidth - width - 8))}px`;
        menu.style.top = `${Math.max(8, trigger.bottom + height + 5 <= window.innerHeight ? trigger.bottom + 5 : trigger.top - height - 5)}px`;
    }
    function clickRecord(event) {
        const row = event.target.closest("[data-id][data-kind]");
        if (!row) return;
        const type = row.dataset.kind, id = Number(row.dataset.id), area = row.dataset.area;
        const button = event.target.closest("[data-action]");
        if (button) {
            const action = button.dataset.action;
            if (action === "more") { openActionMenu(button); return; }
            closeActionMenus();
            if (action === "edit") openWork(type, id);
            else openConfirm(type, id, action);
            return;
        }
        if (event.target.closest(".dashboard-row-toggle")) {
            const queueScroll = get("workList").scrollTop;
            const dayScroll = get("dayList").scrollTop;
            expanded = expanded === `${area}-${type}-${id}` ? null : `${area}-${type}-${id}`;
            renderQueue(); renderDay();
            get("workList").scrollTop = queueScroll;
            get("dayList").scrollTop = dayScroll;
            const list = area === "queue" ? get("workList") : get("dayList");
            list.querySelector(`[data-area="${area}"][data-kind="${type}"][data-id="${id}"] .dashboard-row-toggle`)?.focus();
        }
    }
    function highlightDate(value) {
        document.querySelectorAll(".dashboard-day.linked-hover").forEach((day) => day.classList.remove("linked-hover"));
        if (value) document.querySelector(`.dashboard-day[data-day="${value}"]`)?.classList.add("linked-hover");
    }
    function beginDrag(event) {
        const row = event.target.closest("[data-id][data-kind]");
        if (!row || !row.draggable || event.target.closest("a, input, select, textarea, .dashboard-row-actions")) return;
        dragged = {type: row.dataset.kind, id: Number(row.dataset.id), field: row.dataset.area === "due" ? "deadline" : "date"};
        event.dataTransfer.setData("text/plain", `${dragged.type}:${dragged.id}`);
        event.dataTransfer.effectAllowed = "move";
    }

    document.querySelectorAll("[data-kind][role=tab]").forEach((button) => button.addEventListener("click", () => {
        kind = button.dataset.kind; filter = "all"; shown = 40; expanded = null;
        get("workSearch").value = ""; get("workList").scrollTop = 0; renderQueue();
    }));
    document.querySelectorAll("[data-day-tab]").forEach((button) => button.addEventListener("click", () => {
        dayTab = button.dataset.dayTab;
        expanded = null;
        dayScroll = 0;
        get("dayList").scrollTop = 0;
        renderDay();
    }));
    get("dayViewToggle").addEventListener("click", () => showRightView("day"));
    get("notesViewToggle").addEventListener("click", () => showRightView("notes"));
    get("workSearch").addEventListener("input", () => { shown = 40; get("workList").scrollTop = 0; renderQueue(); });
    get("workFilter").addEventListener("change", (event) => { filter = event.target.value; shown = 40; get("workList").scrollTop = 0; renderQueue(); });
    get("workList").addEventListener("scroll", appendMore);
    for (const list of [get("workList"), get("dayList")]) list.addEventListener("scroll", closeActionMenus);
    window.addEventListener("resize", closeActionMenus);
    document.addEventListener("toggle", (event) => {
        if (!event.target.classList?.contains("dashboard-row-menu")) return;
        const trigger = document.querySelector(`[aria-controls="${event.target.id}"]`);
        if (trigger) trigger.setAttribute("aria-expanded", String(event.newState === "open"));
    }, true);
    get("workList").addEventListener("click", clickRecord);
    get("dayList").addEventListener("click", clickRecord);
    get("workList").addEventListener("pointerover", (event) => {
        const row = event.target.closest("[data-scheduled-date]");
        if (row) highlightDate(row.dataset.scheduledDate);
    });
    get("workList").addEventListener("pointerout", (event) => {
        const row = event.target.closest("[data-scheduled-date]");
        if (row && !row.contains(event.relatedTarget)) highlightDate(null);
    });
    for (const area of [get("workList"), get("dayList")]) {
        area.addEventListener("dragstart", beginDrag);
        area.addEventListener("dragend", () => { dragged = null; highlightDate(null); });
    }
    get("calendarGrid").addEventListener("click", (event) => {
        const day = event.target.closest("[data-day]");
        if (!day) return;
        if (event.target.closest(".dashboard-day-count")) dayTab = "tasks";
        else if (event.target.closest(".dashboard-due-count")) dayTab = "deadlines";
        else if (event.target.closest(".dashboard-event-count")) dayTab = "events";
        selectDay(day.dataset.day);
    });
    get("calendarGrid").addEventListener("dragover", (event) => {
        const day = event.target.closest("[data-day]");
        if (!day || !dragged) return;
        event.preventDefault(); day.classList.add("drag-over");
    });
    get("calendarGrid").addEventListener("dragleave", (event) => {
        const day = event.target.closest("[data-day]");
        if (day && !day.contains(event.relatedTarget)) day.classList.remove("drag-over");
    });
    get("calendarGrid").addEventListener("drop", (event) => {
        const day = event.target.closest("[data-day]");
        if (!day || !dragged) return;
        event.preventDefault();
        const item = dragged; dragged = null;
        day.classList.remove("drag-over");
        moveDraggedTo(day.dataset.day, item);
    });
    function acceptsDayDrop(item) {
        return item && (dayTab === "tasks" && item.type === "task" && item.field === "date" ||
            dayTab === "deadlines" && item.field === "deadline" ||
            dayTab === "events" && item.type === "event");
    }
    get("dayList").addEventListener("dragover", (event) => { if (acceptsDayDrop(dragged)) { event.preventDefault(); get("dashboard").querySelector(".dashboard-day-plan").classList.add("drag-over"); } });
    get("dayList").addEventListener("dragleave", (event) => { if (!get("dayList").contains(event.relatedTarget)) get("dashboard").querySelector(".dashboard-day-plan").classList.remove("drag-over"); });
    get("dayList").addEventListener("drop", (event) => {
        if (!acceptsDayDrop(dragged)) return;
        event.preventDefault();
        const item = dragged; dragged = null;
        get("dashboard").querySelector(".dashboard-day-plan").classList.remove("drag-over");
        moveDraggedTo(selected, item);
    });
    function setPeriod(year, monthNumber) {
        month = new Date(Date.UTC(year, monthNumber, 1));
        if (!selected.startsWith(isoDate(month).slice(0, 7))) selected = isoDate(month);
        renderCalendar(); renderDay();
        get("calendarGrid").parentElement.scrollTop = 0;
    }
    get("calendarMonth").addEventListener("change", () => setPeriod(month.getUTCFullYear(), Number(get("calendarMonth").value)));
    get("calendarYear").addEventListener("change", () => setPeriod(Number(get("calendarYear").value), month.getUTCMonth()));
    get("previousPeriod").addEventListener("click", () => setPeriod(month.getUTCFullYear(), month.getUTCMonth() - 1));
    get("nextPeriod").addEventListener("click", () => setPeriod(month.getUTCFullYear(), month.getUTCMonth() + 1));
    get("calendarToday").addEventListener("click", () => selectDay(data.today));
    function closeAddMenu({restoreFocus = false} = {}) {
        get("dashboardAddMenu").hidden = true;
        get("dashboardAddToggle").setAttribute("aria-expanded", "false");
        if (restoreFocus) get("dashboardAddToggle").focus();
    }
    get("dashboardAddToggle").addEventListener("click", () => {
        const opening = get("dashboardAddMenu").hidden;
        get("dashboardAddMenu").hidden = !opening;
        get("dashboardAddToggle").setAttribute("aria-expanded", String(opening));
    });
    document.querySelectorAll("[data-add]").forEach((button) => button.addEventListener("click", () => {
        closeAddMenu();
        openWork(button.dataset.add);
    }));
    document.addEventListener("pointerdown", (event) => {
        if (!get("dashboardAddMenu").hidden && !event.target.closest(".dashboard-add-wrap")) closeAddMenu();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !get("dashboardAddMenu").hidden) closeAddMenu({restoreFocus: true});
    });
    get("workForm").addEventListener("change", (event) => {
        if (event.target.name === "relationship_type") updateRelationshipFields();
        if (event.target.name === "all_day") updateEventTimeFields();
    });
    function clearFieldError(field) {
        if (!field?.name) return;
        field.classList.remove("is-invalid");
        field.removeAttribute("aria-invalid");
        field.removeAttribute("aria-describedby");
        const trigger = field.closest(".app-select")?.querySelector(".app-select-trigger");
        trigger?.removeAttribute("aria-invalid");
        trigger?.removeAttribute("aria-describedby");
        const slot = [...get("workFormFields").querySelectorAll("[data-error-for]")].find((element) => element.dataset.errorFor === field.name);
        if (slot) slot.textContent = "";
    }
    get("workForm").addEventListener("input", (event) => clearFieldError(event.target));
    get("workForm").addEventListener("change", (event) => clearFieldError(event.target));
    get("workForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        const saveButton = get("workForm").querySelector('[type="submit"]');
        if (workPending) return;
        workPending = true;
        clearWorkErrors();
        saveButton.disabled = true;
        const fields = Object.fromEntries(new FormData(get("workForm")));
        fields.action = recordTarget.id ? "edit" : "add";
        fields.kind = recordTarget.type;
        if (recordTarget.id) fields.id = recordTarget.id;
        if (fields.kind === "task") {
            if (fields.relationship_type !== "property") fields.property = "";
            if (fields.relationship_type !== "issue") fields.issue = "";
        }
        try {
            const operation = recordTarget.id ? "updated" : "created";
            const label = {task: "Task", issue: "Issue", event: "Event"}[recordTarget.type];
            await send(fields);
            get("workDialog").close();
            kind = recordTarget.type; filter = "all";
            await load(); message(`${label} ${operation}.`);
        } catch (error) { showWorkErrors(error); }
        finally { workPending = false; saveButton.disabled = false; }
    });
    get("confirmAction").addEventListener("click", async () => {
        const confirmButton = get("confirmAction");
        if (confirmPending) return;
        confirmPending = true;
        confirmButton.disabled = true;
        try {
            const {type, action} = confirmTarget;
            await send({action, kind: type, id: confirmTarget.id});
            get("confirmDialog").close(); await load();
            const label = {task: "Task", issue: "Issue", event: "Event"}[type];
            const verb = action === "finish" ? {task: "completed", issue: "resolved", event: "marked as occurred"}[type] : action === "cancel" ? "cancelled" : "deleted";
            message(`${label} ${verb}.`);
        } catch (error) { get("confirmError").textContent = error.message; }
        finally { confirmPending = false; confirmButton.disabled = false; }
    });
    document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => {
        const dialog = button.closest("dialog");
        if ((dialog.id === "workDialog" && workPending) || (dialog.id === "confirmDialog" && confirmPending)) return;
        dialog.close();
    }));
    for (const [id, pending] of [["workDialog", () => workPending], ["confirmDialog", () => confirmPending]]) {
        get(id).addEventListener("cancel", (event) => { if (pending()) event.preventDefault(); });
    }

    get("noteForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            await send({action: "add", kind: "note", content: get("noteContent").value.trim()});
            get("noteContent").value = ""; await load(); get("notesList").scrollTop = 0; message("Note added.");
        } catch (error) { message(error.message, {error: true}); }
    });
    get("notesList").addEventListener("click", async (event) => {
        const button = event.target.closest("[data-note-action]");
        if (!button) return;
        const note = button.closest("[data-note]");
        const id = Number(note.dataset.note);
        const action = button.dataset.noteAction;
        if (action === "edit") { editingNote = id; renderNotes(); get("notesList").querySelector(`[data-note="${id}"] textarea`).focus(); return; }
        if (action === "cancel") { editingNote = null; renderNotes(); return; }
        try {
            if (action === "delete") await send({action: "delete", kind: "note", id});
            else await send({action: "edit", kind: "note", id, content: note.querySelector("textarea").value.trim()});
            editingNote = null; await load(); message(action === "delete" ? "Note deleted." : "Note updated.");
        } catch (error) { message(error.message, {error: true}); }
    });
    get("dashboardToastClose").addEventListener("click", hideToast);
    document.addEventListener("pointerdown", (event) => {
        if (!get("dashboardToast").hidden && !get("dashboardToast").contains(event.target)) hideToast();
    });
    load();
});
