# APP-009 · Full-app dropdown audit (code inspection)

Status: investigated; no UI changes made. The form-select decision is already settled by APP-005 (shared custom treatment on all Dashboard selects). This covers the current templates, form widgets, CSS and JavaScript. Browser/device interaction still needs verification before an accessibility claim.

## Inventory

| Surface | Select controls | Current open-menu mechanism |
| --- | --- | --- |
| My Work: Tasks, Issues, Events | Sort/filter selects; relationship, priority, property and other form selects in Bootstrap modals | `select.form-select` is enhanced by `searchable-select.js` at `DOMContentLoaded`. Property/issue and lists over 12 options gain search; short lists use the same custom popup without search. |
| Properties | Sort/state in the left header; type/status/sort in related records; form selects in modals | Same shared enhancement. The cramped header is a layout/sizing problem (`property-control-row` uses fixed 6.5rem/8.25rem second tracks), not a separate select engine. |
| Contacts | Sort/state in the left header; contact-method type in a modal | Same shared enhancement. |
| Dashboard | Operations filter, calendar month/year, and dynamically built Add/Edit form selects | Native `<select>` menus. These elements lack `.form-select`; modal selects are also created after the shared component's one-time scan. Their blue option highlight is browser/OS rendering. |
| Profile/account and notes | No select menus found in current templates/forms | Not applicable. |

Action menus are a separate family: navbar/account and My Work/Property/Contact kebabs and Property `+ Add` use Bootstrap dropdowns. Dashboard `+ Add` is a hand-built menu; its compact row overflow menus use the browser Popover API. They should not be confused with form selects in design or tests.

## Shared picker behavior and risks

`searchable-select.js` hides the original select, inserts a button and listbox, mirrors selection through a `change` event, and positions its popup above/below according to viewport space. Popups live in the nearest Bootstrap `.modal` or the document body. It supports arrows, Enter, Escape, Tab and typeahead, but has no public initializer for newly inserted controls—only `refresh(select)`—and no native `<dialog>` popup/focus integration. The Dashboard APP-005 decision (use the shared treatment for all its selects) therefore needs a component extension, not only CSS classes.

The Property header screenshot's differing widths arise from its grid/button sizing and narrow one-third pane. The open select treatment there is otherwise the shared one used by other supporting pages. Dashboard is the genuine native-versus-custom exception. Existing dropdown menus also have different implementations; replacing them all would be a separate decision, not required by APP-005.

## Recommendation for discussion

Keep the shared select component as the app convention, implement the already-selected APP-005 treatment for Dashboard after adding dynamic initialization and `<dialog>` support, then align closed-control dimensions via APP-002/PROP-001. Do not infer that every action menu needs the select component. For the next UI pass, preserve the existing action-menu implementations unless interaction testing reveals a concrete failure; no general action-menu rewrite has been requested.

## Verification still required

- Keyboard and screen-reader labeling/selection for short and searchable lists, especially modal focus return.
- Touch opening, scrolling, and option selection on narrow screens; zoom and viewport-edge positioning.
- Dashboard `<dialog>` stacking/focus after APP-005 integration; Bootstrap modal popup clipping.
- Submitted values and dependent filters (Task relationship, Event participation/presence) after picker selection.
- Property and Contact header sizing at desktop, iPad and narrow phone widths.

Sources: `static/js/searchable-select.js`, `static/css/site.css`, `static/css/property-workspace.css`, `static/js/dashboard.js`, and current templates/forms for Tasks, Issues, Events, Properties, Contacts and Dashboard.
