# Product issue backlog

Short, stable IDs for observations raised during UI review. This is an intake log, not a list of agreed solutions. Keep IDs unchanged when an item is investigated, split, or moved to a GitHub Issue. Add links to the eventual issue or PR beside the ID.

Status values: **Open** (recorded), **Investigating**, **Ready**, **Done**. Unless noted otherwise, these items came from the dashboard review on 25 September 2026. The three dashboard screenshots supplied in that discussion show expanded task, issue, and event rows.

## Dashboard interaction and presentation

### DASH-001 · Record expand/collapse affordance

- **Category:** Interaction / visual clarity · **Status:** Open
- The small down arrows on dashboard task, issue, and event rows are hard to read and feel visually awkward. Revisit the icon and its placement consistently across all three types.

### DASH-002 · Blue accent usage

- **Category:** Visual system · **Status:** Open
- The My notes button and calendar hover / linked-date highlight use blue-tinted states that may not fit the rest of the app. Review these together as one colour-system decision, including selected and hover states.

### DASH-003 · Expanded record hierarchy and controls

- **Category:** Interaction / layout · **Status:** Open
- Expanded task, issue, and event rows feel bland on desktop. Action buttons are too easy to miss, and the “Open full record” link and label/value layout need review. Compare all three expanded states, including long content.

### DASH-004 · Calendar cell height and density

- **Category:** Layout · **Status:** Open
- Month-view day cells stretch vertically to fill the panel. Test a denser calendar and the balance between the date/control header and calendar grid without losing the full-height three-column layout.

### DASH-005 · Three panel headers

- **Category:** Layout / visual consistency · **Status:** Open
- Operations, calendar, and selected-day headers differ in height, background, and hierarchy. The selected-day header is taller and reads too much like another record. Review them as one coordinated set.

### DASH-006 · Selected-day heading

- **Category:** Information hierarchy · **Status:** Open
- Make the chosen date and its task/event summary clearly distinguishable from the records beneath it. Track separately from overall header alignment so the content hierarchy is not lost.

### DASH-007 · Useful calendar signals

- **Category:** Information design · **Status:** Open
- Calendar cells currently show task and event counts. Investigate whether issue deadlines and other actionable date signals belong there, and how to distinguish a deadline from scheduled work without overloading a cell.

## Cross-app consistency

### APP-001 · Search, filter, and sort behavior audit

- **Category:** Cross-app audit · **Status:** Open
- Inventory every search/filter/sort control across Dashboard, My work, Properties, Contacts, and related views. Compare instant versus Apply-driven behavior, client-side versus server-side execution, data coverage, sorting, and state restoration. Dashboard currently filters loaded records in JavaScript; other pages have not yet been audited.

### APP-002 · Search and filter control styling audit

- **Category:** Cross-app audit / visual consistency · **Status:** Open
- Compare sizes, spacing, and placement of dashboard search/select controls with corresponding controls elsewhere. Decide on a shared presentation after the behavior audit.

### APP-003 · Workspace width across devices

- **Category:** Responsive layout · **Status:** Open
- Dashboard uses a wider custom shell/grid than My work, Properties, and Contacts. Review whether those supporting workspaces should use more desktop and iPad width too, without assuming they should adopt the dashboard's three-column structure.

### APP-004 · Recognising work-item types at a glance

- **Category:** Visual system / information hierarchy · **Status:** Open
- Tasks, issues, and events currently require too much reading to tell apart in dashboard lists and the selected-day panel. Develop a restrained, consistent type cue that works alongside existing priority and status colours.
