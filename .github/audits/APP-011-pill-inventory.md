# APP-011 · Status, priority and timing pill audit (code inspection)

Status: option A selected on 26 September 2026; no UI changes made. The inventory distinguishes semantic badges from count badges and filter chips. Visual/device verification remains to do.

Three visual treatments are compared in `../../wireframes/ui_audit/03_pill_system.html`. The user selected A: common pill geometry and typography, with the existing semantic colours retained.

## Inventory

| Meaning | Current rendering | Mismatch |
| --- | --- | --- |
| Task/Issue priority | Shared `includes/work_priority_badge.html` and `.work-pill--priority-1..4` (grey, blue, amber, red) in My Work and Properties | Dashboard recreates similar priority badges with `.dashboard-priority`, smaller sizing and slightly different colours. |
| Task/Issue lifecycle | Shared `.work-pill--active` (green) and `.work-pill--terminal` (grey) | Contact active/deactivated uses Bootstrap badge utilities rather than the shared primitive. Property heading does use `work-pill`. |
| Task/Issue deadline urgency | Shared `.work-pill--soon`, `--missed`, `--overdue` (amber/red) in My Work and Properties | Dashboard uses its own amber due-count badges; those are calendar signals rather than record-state pills, but should harmonize. |
| Event state | `.event-state-badge` with scheduled blue, occurred green, cancelled grey in Events | Properties uses `.property-event-badge` (another blue treatment) and `.property-outcome-badge` for history. Dashboard event rows use no equivalent state pill because they show only scheduled events. |
| Presence requirement | `.property-presence-badge` grey in Property related records | No shared equivalent; this is metadata, not lifecycle status. |
| Counts and filters | Bootstrap count badges in My Work; custom count badges in Dashboard tabs; issue filter chips | These denote quantity/active filters, not record state. They should not inherit priority/status colours. |

The common `work-pill` primitive already fixes height (1.35rem), padding (0.1rem 0.45rem), radius (0.3rem), weight (650) and border. Event badges are close but use a different radius, padding and weight. Contact badges use Bootstrap defaults and read especially faint in the detail heading. Properties has additional purpose-built classes with similar geometry but separate CSS declarations. Dashboard defines an independent compact system.

## Recommendation for discussion

Use one shared base geometry/typography for semantic pills, with semantic variants for **priority**, **lifecycle**, and **timing**. Preserve meanings: blue medium priority is not the same thing as blue scheduled event; a deadline alert is not a record type. Contact Active should use the shared lifecycle treatment, while Event scheduled/occurred/cancelled should map to explicit state variants. Keep count badges and filter chips as separate primitives. Avoid solving this by changing labels or business state.

Placement needs its own rule: priority can appear in compact rows; lifecycle should appear when not obvious from context; timing belongs beside a relevant date; repeated badges in a detail heading and nearby status card may be redundant. Test long titles and narrow widths so pills do not squeeze the record name.

## Verification still required

- Compare actual rendered colours and contrast in normal/hover/focus states on desktop, iPad and phone.
- Check repeated badges in Task/Issue detail headers and status cards, Property related records, Event lists and Contact detail.
- Check wrap/truncation with long titles, especially Contact mobile header and Dashboard compact rows.
- Confirm accessible text remains visible; colour alone must not carry meaning.

Sources: `templates/includes/work_priority_badge.html`, `templates/includes/work_state_badge.html`, `static/css/site.css`, `static/css/event.css`, `static/css/property-workspace.css`, `static/css/dashboard.css`, and current Task, Issue, Event, Property and Contact templates.
