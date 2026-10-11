# Decisions made along the way

Decisions taken without asking while the rework (#557) and its prerequisites were built, because doing them made clearly more sense than not. They are collected here for one review once the epic is through. Decisions that were asked and answered are in the [README](README.md#decisions), not here.

Each entry says what was decided, why, and where it landed.

## Prerequisites on `main`

### Token usage and cost (#571, PR #575)

- **Usage is collected where it is spent.** Engines call `report_usage()` the moment a model answers, and the agent prices the run once at the end. A failed run therefore still reports what it used: a chain whose later engine fails, a failing escalation tier, or a DSPy prediction that fails validation. This replaced merging usage through every `EvalResult`.
- **An unknown price is `null`.** `cost_usd` stays `null` in the API when a model has no price, and the Run Status tab shows no cost for it.
- **A shadow request cancelled at its timeout is not counted.** It returns no usage, and keeping the run open for it would undo the shadow's promise never to hold up a decision. This is documented.
- **Run durations use the monotonic clock,** per AGENTS.md (WSL2 clock steps).

### Activity histogram (#572, PR #576)

- **Buckets are computed in integer microseconds, in SQLite and in Python alike.** `julianday()` rounding put edge artifacts in the wrong bucket.
- **Ranges too wide for 64-bit arithmetic are rejected** (422; about 584 years at 500 buckets).
- **SQLite gets an index on `created_at`,** so the dashboard's last-hour histogram reads only its range.
- **Visibility for identified callers stays as in the list and summary endpoints:** query, then filter per artifact. Pushing visibility into the stores would change all three endpoints.
- **The Dapr store's type-name filtering is left as it is** and filed as #577. It affects every query, not just the histogram.

### Engine tag and failed agents (#583, #585, PRs #584, #586)

- **`subscriptionGroups` and `lastError` on agent nodes,** so the card can label `AND`/`JOIN` rows and say why an agent failed after a reload.
- **A failed agent stays in `error` until it runs again.** The collector used to set it back to `idle` and broadcast `agent_completed` right after `agent_error`.
- **Versions:** 0.5.770 (usage), 0.5.771 (histogram), 0.5.780 (engine tag, a new series), 0.5.781 (its follow-up for #560).

### Flaky tests and small fixes found along the way

- **#578 (PR #579):** the publish panel's tests chose a type before the types had loaded. 12 of 15 failed with a 20 ms delay.
- **#581 (PR #582):** the keyboard shortcuts were registered twice and cancelled each other out. Fixed on `main` as well, since the released dashboard has the bug.
- **#587 (PR #588):** `LiveOutputTab.test.tsx` asserted wall-clock durations (`< 50 ms`) against a mock from the test file; the real tab does not virtualize. The mock and its tests were removed rather than adding virtualization to a component #561 replaces.

## Rework items

### #558 Tokens and themes (PR #574)

- **The legacy palette names point to the tokens** until each component is rebuilt, so the old dashboard stays usable on the new themes.
- **Terminal themes get a contrast guard (4.5:1) and `--on-*` text colors** for solid signal fills.

### #559 Shell (PR #580)

- **The search field is shown but disabled** until the command palette (#568) wires it.
- **The Agent Details button is gone.** Ctrl+Shift+D still opens the detail windows until nodes unfold in place (#561).
- **"Clear all dashboard data" moved to Settings › Advanced now** rather than in #569, so it is never missing.
  - It clears only the dashboard's own database and settings, where it used to clear every database and key of the origin.
  - It waits for the deletion before it reloads, asks to close other dashboard tabs that block it, and reports a failure.
- **Open panels are not saved,** so the dashboard always opens on the board.
- **Empty states:**
  - "Nothing on the blackboard yet" when the blackboard is empty;
  - "Nothing matches these filters" (with Show all) when filters hide its artifacts;
  - "Nothing to show here" while the blackboard's size is unknown.
- **The live status counts agents only in the Flow view;** the Blackboard view's nodes are artifacts.
- **Reconnecting:**
  - a failed connection is retried like a dropped one, with the countdown in the store;
  - Retry now counts as an attempt and does nothing while an attempt is under way;
  - a reconnect reloads the board and the summary, and drops live states from before the outage.
- **The filter popover's controls (presets, multi-selects) are on the tokens.** The blue and red fills were the wrong signals.
- **Ctrl+F opens the filters on the correlation search,** until the command palette replaces it.
- **Settings shows the dashboard version from `package.json`** (it said 0.1.1).

### #560 Agent cards, chips and edges

- **Backend prerequisites as PRs on `main`:**
  - `subscriptionGroups` and `lastError` for the `AND`/`JOIN` rows and the error row (#585, PR #586);
  - the collector derives the agent status from its runs and puts it on the run events, so concurrent runs do not flip the card.
- **The error row opens the existing trace viewer module** on the run's correlation ID (`ModuleInstance.search`) until the Traces tab (#561) and the timeline dock (#564) replace it.
- **"In flight" means:** a run of the edge's target agent consumed that type (`consumed_types` of `agent_activated`) and has not ended. Runs are tracked by `run_id`, so one ending leaves a concurrent run's edges moving.
  - A dashboard that connects while a run is under way shows that run's edges still, until the next activation; its status dot is right. Seeding them from the snapshot needs the active runs' types from the server, and a snapshot that arrives after a run's `agent_completed` would keep that run in flight for good. The edge animation setting now means "animate edges in flight"; the global always-on animation is gone.
- **A subscription that needs a type several times** (`.consumes(A, A, A)`) shows one row with `×3`.
- **Subscriptions that would show the same row show it once.** The server labels and counts by type, so `.consumes(Route.billing).consumes(Route.shipping)` reads `◆ Route.billing | Route.shipping` with one count. A row per handle needs counts per subscription from the server.
- **Decision handles about the same subject read `AND`** (`pager`: `Route.tech AND Urgent.yes`), although they correlate like a join under the hood; `JOIN` is kept for joins by a key.
- **The demo does not record traces,** so the error row's trace viewer opens empty there; the link carries the run's correlation ID.
- **The chip shows the received count** as its one count.
- **Join keys:**
  - shown without the tuple quoting;
  - long keys (ids) keep their first 8 characters;
  - more open keys show as `+N`.
- **A batch shows one cell per item up to 24,** then a bar.
- **Countdowns of joins and batches go on from the server's,** taken when the snapshot arrived, on the browser's monotonic clock. The browser's clock never has to agree with the server's.
  - Both countdowns turn amber under 30 s (the design names it for joins).
  - The oldest open join is taken over all of the agent's joins.
- **The status dot is labelled** (`running`, `failed`, `idle`) for screen readers, since a chip has no other status text.
- **Removed settings:**
  - agent colors, node shadow, status pulse and compact view: status colors are the signals, and the chip level replaces the compact view;
  - the default edge width is 1.5 px, per the design.
- **The board background is the dotted `--board`;** the old canvas controls stay until the canvas dock (#563).
- **Decision summaries inside cards keep their current look** until the decision kit (#566).


### #561 Unfold a node in place

- **Backend prerequisites on `main`:**
  - agent nodes carry `description` and `model`, the model resolved as the agent gets it at run time (#592, PR #593);
  - the dashboard read its traces from `.flock/` next to the installed package while the tracer writes to the working directory, and looked for the file only at startup; it now reads the working directory's file on every request (#594, PR #595). Until then the trace viewer, and the Traces tab, showed nothing.
- **One node is unfolded at a time,** as the issue proposed. It stays unfolded when the board zooms out to chips; it is what the reader looks at.
- **Making room:**
  - a hierarchical layout reruns with the unfolded size (the design's rule);
  - circular, grid and random arrangements keep their shape and get room inserted: what lies right of the card moves right by the width it gains, what lies below moves down, so nothing that was apart overlaps;
  - the unfolded node keeps its top-left corner, so it opens where it was clicked;
  - folding puts every node back, animated like the unfolding.
  - the board then pans as little as it takes to show all of the unfolded node (24 px margin, no zoom); a card at the edge used to unfold under the header.
- **Positions while a node is unfolded are not saved,** and snapshot refreshes keep them (they win over the saved ones). Moving a node meanwhile lasts until the node folds. A layout that comes due meanwhile (new nodes or edges) waits for the fold, which then lays the board out anew; choosing a layout from the menu folds the node first and lays the board out in that mode.
- **Keys:**
  - Space and Ctrl+Shift+D unfold or fold the focused agent, else the selected one, else the unfolded one; Space is left to buttons, fields, tabs and dialogs that have the focus.
  - Esc folds the unfolded node once the panels are closed (it used to close the detail windows), and leaves an Esc that a dialog already handled.
  - Space no longer pans the board (`panActivationKeyCode`); dragging the board pans it.
- **Artifact detail windows stay** until artifact cards unfold in the Blackboard view (#565); they open with a double-click and are no longer saved.
- **Removed with the agent windows:** the three tabs, the stream store, and their tests, which tested mock components defined in the test files rather than the tabs.
- **Tabs:**
  - Live starts from the server's streaming history on every opening and adds live events it does not have yet, so reopening never repeats output (the old tab appended the history again each time); it follows the end while scrolled there, without a switch.
  - History reloads when the agent's counts change; Runs and the Overview reload when its status or counts change, and every 3 s while it runs, since a busy agent's runs start and end while it stays `running`.
  - The Overview sums tokens and cost over the runs the server lists (the latest 50, labelled so); unpriced runs add tokens, not cost.
  - Traces reads the agent's latest five runs from a new endpoint, `/api/traces/agents/{name}` (`Agent.execute` spans by `agent.name` and the spans below them, #597, PR #598), since `/api/traces` returns the whole trace database; "Open in the trace viewer" stays until the timeline dock (#564).
- **Not yet:** the focus button (#562) and the decider's review queue (#566). Until the decision kit, a decider's model shows both under its name and in its answers.
