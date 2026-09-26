# Follow-up backlog · UI, behavior, and migrations

Started 26 September 2026. This is a fresh intake log for work raised after the earlier UI audit and implementation pass. It does not replace the older local `docs/KNOWN_ISSUES.md` or imply approval to implement an item. Keep IDs stable; record decisions and eventual PRs beside them.

Use **UI** for visual/layout changes, **BEH** for interaction or data-behavior problems, and **MIG** for migrations or structural changes. Review and fix these as separate passes. Statuses: Open, Investigating, Ready, Done.

## Behavior pass

### BEH-001 · Same-day dashboard drop reports a move

- **Status:** Open · **Area:** Dashboard drag-and-drop / feedback
- **Observed:** Dragging an item from Selected day and dropping it back on that same calendar day shows a success toast saying the task deadline was moved. Dragging an already-scheduled task onto its existing scheduled day also reports a move, although its date did not change.
- **Expected:** An unchanged date should not be presented as a reschedule. The exact no-op interaction and feedback can be decided during the behavior pass.
- **Investigate:** Check all drag sources and date targets, including scheduled task dates, task/issue deadlines, and all-day/timed events, for the same pattern. Confirm whether an unnecessary POST or database write occurs, not only whether the toast is misleading. Check keyboard/tap date-change alternatives too.
- **Verification:** Same-date drop versus genuinely different-date drop; Selected day and Operations sources; no misleading toast, no unintended mutation, and unchanged selection/counts on a no-op.

### BEH-002 · Drag source is highlighted as a drop destination

- **Status:** Open · **Area:** Dashboard drag-and-drop / target feedback
- **Observed:** When dragging an item out of the Selected day pane, that same selected-day area highlights as though it were a valid place to drop the item. Reported while viewing Deadlines; check the Tasks and Events tabs as well.
- **Expected:** The drag source should not advertise itself as a destination for an unchanged item. Selected day may still be a valid destination for a record dragged from elsewhere, where dropping it would actually change its date.
- **Investigate:** Trace target eligibility and highlight classes for every drag source/type. Check whether the misleading highlight is only visual or whether the pane also accepts a no-op drop; coordinate with BEH-001 without merging the two symptoms.
- **Verification:** Drag from each Selected day tab and from Operations; only valid destinations highlight, and the source remains visually distinct from drop targets.

### BEH-003 · Unchanged note edit still reports an update

- **Status:** Open · **Area:** Dashboard My notes / save feedback
- **Observed:** Open a note for editing, leave its content unchanged, and press Save. The UI sends an edit request, reloads the dashboard data, and shows “Note updated.” even though the user made no change.
- **Expected:** Saving unchanged content should not claim an update or make an unnecessary write. Decide whether Save should be disabled until the text changes or should quietly close the editor on an unchanged submission.
- **Investigate:** Compare the edited value with the stored note after the same trimming/normalization used on submit. Check whether a server-side no-op guard is also warranted. Verify that a real edit, validation failure, and retry retain their current feedback.
- **Verification:** Unchanged Save, whitespace-only difference, actual edit, and failed edit; no misleading success toast or write for the no-op case.

## UI pass

No new items logged yet. Add presentation issues here without mixing them into behavior fixes.

## Migration / structural pass

No new items logged yet. Record any proposed migration separately, with its reason and scope, before approving implementation.
