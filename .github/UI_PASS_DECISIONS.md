# Next UI pass · centralized decisions

Last reviewed: 26 September 2026. The user authorized this pass, and the agreed changes are implemented in the working tree on `chore/further-ui-housekeeping`. Keep IDs linked to the existing known-issues log. Automated tests pass; authenticated desktop, iPad and narrow-mobile browser acceptance remains for the user's session.

## Agreed; implement in the next pass

| ID | Decision and scope | Verification |
| --- | --- | --- |
| DASH-008 | Keep the Dashboard's `fetch`/JSON modal flow; do not add a redirect or `form_state` URL. Preserve values on validation error, display field errors beside their fields and non-field errors in the dialog, use a friendly error for non-JSON/network failures, and keep confirmation/background-action failures visible without losing context. A fresh Add/Edit open starts clean. | Error → correction → retry; Cancel, X, Escape, reopen and refresh; pending/double-submit behavior; accessible error association and focus. Existing endpoint tests do not cover this browser lifecycle. |
| WORK-001/002 | On mobile, use the same clear, standard chevron/disclosure control for Tasks, Issues and Events. A tap expands the row inline for useful detail and available quick actions; include an explicit **Open record** link to the full detail view. Preserve the desktop/iPad split pane and current list query/filter context. | First tap and collapse behavior, selected URL/history, long text, linked records, modal targets, keyboard and 44px-ish touch target. Do not duplicate all full-detail content inside every row. |
| PROP-001 | Rebalance spacing, heights and proportions of the existing Properties list-header controls within its current pane. Keep GET/Apply behavior and postpone the wider-shell experiment. | Search width, Add/Apply sizing, sort/state labels and popup positioning across widths. |
| PROP-002 | Replace whole-row related-record navigation with an inline expand/collapse preview plus a separate explicit **Open record** link. Preview description, relationship, relevant dates and state; deeper actions remain on the record page. | No nested interactive links; preserve property context, filters, pagination and scroll; long text, inactive records, keyboard/touch. |
| CONT-001 | Distinguish Telephone/Email card headings from values, with modest heading treatment. Remove the double divider between heading and first row. | Empty/populated cards at desktop, iPad and phone widths. |
| CONT-002 | On mobile, use the full width for the contact name and let long names wrap rather than relying on the two-line clamp/title tooltip. Put a flexible Edit/Reactivate action beside a fixed-width kebab in a full-width action row. Leave desktop/iPad header intact. | Short and stress-test names, narrow screens, status/date wrapping and touch targets. |
| APP-002 | Match Dashboard search and filter control styling to the shared form vocabulary. Keep Dashboard instant filtering and other pages' submitted GET forms. | Visual and focus states; no behavioral regression. |
| APP-004 | Use restrained icon + visible Task/Issue/Event text in mixed work-item lists, notably selected-day Deadlines. Do not repeat type labels in single-type Operations tabs. | Dense/mobile rows and colour-independent recognition. |
| APP-005 / APP-009 | Use the shared custom select treatment for **all Dashboard selects**, including dynamically created Add/Edit fields, Operations filter, and calendar month/year; short lists need no search box. Extend shared initialization and native `<dialog>` portal/focus handling. Existing My Work/Properties/Contacts selects already use the shared component, so APP-009 does not require a second select-system decision. Action kebabs/Add menus are a separate family: retain existing mechanisms in this pass unless interaction testing finds a concrete bug. | Keyboard, screen reader, touch, modal stacking, viewport edge, dependent fields, submitted values. See `audits/APP-009-dropdown-inventory.md`. |
| APP-006 | Use the shared neutral focus treatment for Dashboard modal fields, visibly distinct from validation error styling. | Keyboard focus, 200% zoom and browser native date/time controls. |
| APP-010 | Align Contact notes and Dashboard My notes on the same quiet SVG pencil/cross controls, target sizing and hover/focus/touch visibility. Keep note data and deletion behavior unchanged. | Narrow note cards and touch actions. |
| APP-011 | **Option A:** use one shared semantic-pill geometry and typography while retaining the existing meaningful priority, lifecycle and timing colours. Bring Contact Active, Event state, Property-specific and Dashboard pills into that system; keep count badges and filter chips separate. Do not use colour alone to identify record type. | Rendered contrast, placement, repeated badges, long names/titles and mobile wrapping. See `audits/APP-011-pill-inventory.md` and the option-A wireframe. |

## Parked by the user

- DASH-012: touch drag gesture. Existing tap/date alternatives remain; no touch-drag implementation in this pass.
- APP-003: wider Properties-shell experiment and any wider rollout.
- APP-007/008: branding and mobile Logout treatment.

APP-001 is settled with no implementation: retain Dashboard client-side quick filtering and Django GET filtering elsewhere. Dashboard redesign decisions already built are not repeated here.
