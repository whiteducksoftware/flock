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
- **Positions while a node is unfolded are not saved,** and snapshot refreshes keep them (they win over the saved ones). Moving a node meanwhile lasts until the node folds. A layout that comes due meanwhile (new nodes or edges with auto layout on) waits for the fold, which then lays the board out anew; with auto layout off the fold puts the nodes back and leaves new ones where they appeared. Choosing a layout from the menu folds the node first and lays the board out in that mode.
- **A click on a control inside a card** (the failed run's trace button, a review button) does only what the control does; it does not unfold the card.
- **Keys:**
  - Space and Ctrl+Shift+D unfold or fold the focused agent, else the selected one, else the unfolded one; Space is left to buttons, fields, tabs and dialogs that have the focus.
  - Esc folds the unfolded node once the panels are closed (it used to close the detail windows), and leaves an Esc that a dialog already handled.
  - Space no longer pans the board (`panActivationKeyCode`); dragging the board pans it.
- **Artifact detail windows stay** until artifact cards unfold in the Blackboard view (#565); they open with a double-click and are no longer saved.
- **Removed with the agent windows:** the three tabs, the stream store, and their tests, which tested mock components defined in the test files rather than the tabs.
- **Tabs:**
  - Live starts from the server's streaming history on every opening and adds live events it does not have yet, so reopening never repeats output (the old tab appended the history again each time); it follows the end while scrolled there, without a switch. It keeps the text, not the events, and shows the latest 100,000 characters: a history can hold 100,000s of events.
  - History reloads when the agent's counts change; Runs and the Overview reload when its status or counts change, and every 3 s while it runs, since a busy agent's runs start and end while it stays `running`.
  - The Overview sums tokens and cost over the runs the server lists (the latest 50, labelled so); unpriced runs add tokens, not cost.
  - Traces reads the agent's latest five runs from a new endpoint, `/api/traces/agents/{name}` (`Agent.execute` spans by `agent.name` and the spans below them, #597, PR #598), since `/api/traces` returns the whole trace database; "Open in the trace viewer" stays until the timeline dock (#564).
- **Not yet:** the focus button (#562) and the decider's review queue (#566). Until the decision kit, a decider's model shows both under its name and in its answers.

### #562 Focus mode

- **A double-click unfolds the card and puts it in focus** (the first click unfolds); leaving focus returns to the unfolded node. Esc leaves focus before it folds, and Space and Ctrl+Shift+D do not reach the board behind the stage.
- **The stage covers the board, not the header,** so filters and the publish panel stay reachable; it is therefore a dialog that is not modal (`aria-modal` is not set). It ends by itself when its node leaves the board (the other view).
- **Lineage comes from the graph's edges:** the producers of what the agent reads, a decision handle one step further back to the subject the decider read (as in the mockup), the node, its outputs and their consumers with the option a decision consumer takes. Only a handle subscription (its `◆` type label) leads back to the subject; a consumer of the decision itself (`Decision.of(Route)`) shows the decider and the question. Edges that have not carried anything yet (an open join, a batch) are not in it.
- **Live's right column** shows the input: while the agent runs, the latest started run's inputs (every one of an AND gate or batch, up to five read, the rest and those the dashboard may not read counted; images as thumbnails), read by ID from the run's start event (for a handle, the decision's subject, for a consumer of the decision itself the decision; images as thumbnails; the history has a run's input only once the run has published; "Not known for this run" for a run that started before the page connected), else the latest consumed message. While the agent runs, it shows that run's output (the end of each running run's stream is kept apart, since the card's ticker mixes overlapping runs; the ticker when no run is known) as the output so far ("Waiting for output" until the first; never an earlier run's output), else the latest published message; earlier runs open the Runs tab. The header says how long the running run has run, or how long ago the last run ended, counted on the monotonic clock after one wall clock reading. A run that fails drops the card's and the stage's tokens, so the next run does not start with them. The engine's class name in the mockup (`DSPyEngine`) is the card's tag (`LLM`) next to the model.
- **Contract:** fields with type, `?` for optional ones and the description; a decision handle shows the subject's fields (each subject's, when the deciders that bring it decide about several types; a reviewed decision comes from the reviewer, so then every decider of the question counts; in a screening network, the handles a decider reads lead back to their subjects), a decider's decisions only that they route to their handles. Visibility is not shown; agent nodes do not carry it.
- **History loading moved into a hook** (`useMessageHistory`) shared by the History tab and Live's right column.
- **The tablists of the unfolded node and the stage follow the WAI-ARIA tabs pattern** (arrow keys, Home and End, one tab in the Tab order).

### #563 Canvas dock

- **The lock of the React Flow controls is not in the dock** (the design's dock has none, and it was rarely of use); nodes can always be moved. The README's table maps "React Flow controls (zoom, fit, lock)" to the dock.
- **Until the timeline dock (#564), the trace viewer and the historical blackboard open only from where they are linked** (a failed run's row, the Traces tab's link); the historical blackboard has no entry point for that time. This is a state of the `ui-rework` branch only.
- **Choosing a layout keeps it as the board's layout** (as the right-click menu did), and folds an unfolded node first; Auto-arrange is the old "Auto Layout: On/Off".
- **The layout menu is a WAI-ARIA menu of radio items** (arrow keys, Home, End, Esc back to its button; Tab, Shift+Tab or a focus that leaves it closes it); its Esc does not reach the board's shortcuts.
- **The layout direction setting** (Settings › Advanced) now says it is the default hierarchical layout's direction; the dock's menu picks one too. Settings are reworked in #569.
- **Zooming and fitting do not animate for people who ask for less motion.**

### #564 Timeline dock

- **The histogram shows the last hour in 60 one-minute bars,** reaching further back when a custom range starts earlier, and refreshes every 10 s once the last answer is in (a slow server would never answer in time otherwise). Counts of other filters are dropped at once; "Activity not available" when the new ones fail. It counts for the board's filters (correlation, types, producers, tags, visibility) but not for its time filter, which the brush shows.
- **A brush that ends within a bar of now stays open,** so it follows the time; one as long as a preset (5 min, 10 min, 1 hour; the closest one, within a bar) is that preset, so brushing and picking it make the same filter. Other brushes are fixed custom ranges. A range with a start only is read that way everywhere: History asks from its start, the time chip says "Since …", and the graph snapshot already took open bounds.
- **The dock's tabs split the trace viewer's views:** Traces holds the timeline and statistics, Metrics the RED metrics and dependencies, Tracing settings the configuration and guide; the History tab is the historical blackboard. The search box shows only for the views that list traces. The search lives in the dock's state: it outlives a tab change, and a trace link replaces it.
- **Histogram requests use relative `/api` paths** like the graph snapshot and the other dashboard requests; `VITE_API_BASE_URL` is honored only by `services/api.ts` and the theme service, so one more call on it would not make the dashboard work on another host.
- **Trace search syntax:** `agent:NAME` (spans with that `agent.name`), `status:error|ok`, `service:CLASS` (the class in a span's name, any case); other words search trace ids, span names and attribute values as before. Sorting: Newest, Slowest, Errors first, Spans.
- **While the dock is open, agents show as chips and the canvas dock and minimap are hidden;** the board is too short then for cards and controls on top of it. The board keeps 220 px. Expanding the dock fits the graph into that strip (else it may show none of it), and collapsing gives the view back.
- **A time range never holds an invalid bound:** a cleared or half-typed date field leaves the range as it was, and every reader (histogram, History, the chip, the graph request) takes a bound only when it is a time, since an older dashboard stored NaN, which a reload makes null.
- **Focus mode and the expanded dock exclude each other,** since each needs the board's room (the stage would shrink to the 220 px board): opening the dock, also from a trace link in focus mode, leaves focus mode, and the node stays unfolded; focusing a node collapses the dock.
- **Esc** closes panels, then leaves focus mode, then collapses the dock, then folds the unfolded node, then closes artifact windows.
- **Services in the trace viewer get neutral greys** instead of eight hues, since the design keeps color for its four signals; errors are coral. Its emoji are gone (icons for empty and error states).
- **The floating module windows are gone with their registry, store and persistence.** The `flock-module-state` key is removed by "Clear all dashboard data"; the `module_instances` store stays in existing IndexedDB databases (removing it needs a version upgrade of the database for no gain) and is no longer written.

### #565 Blackboard as run lanes

- **The lanes come from the Blackboard's graph snapshot** (the newest 500 artifacts for the board's filters, with their decision views and the edges from what a run consumed to what it published); a note points to the table when the snapshot is cut off. The view no longer uses React Flow, so its saved positions are gone (the `layout_blackboard_view` store stays in existing IndexedDB databases, unused).
- **Columns are depths in that graph:** an artifact sits one column after the deepest artifact it came from, so decisions about one subject share a column; depths with nothing in a lane (inputs from another run) close up. The server draws a run's edges once the run is done, so what a running run published, or just streamed, goes after what the run consumed (its start event names it).
- **Arrows:** dashed when everything in the next column came from unsure decisions, amber when something there is being made; a plain arrow otherwise.
- **Lane status:** running wins ("triage is deciding" for an agent that published decisions, "is writing" while it streams, else "is running"; "triage and 1 more are working"), then "needs review" (an unsure decision, not a checklist's unsure items, without a review, and "answered by" whoever consumed it meanwhile), else "done in 3.5 s · 5 artifacts" (first to last artifact).
- **Lane title:** a field that names the artifact (`title`, `subject`, `name`, `question`, `summary`), else the first text of the payload.
- **A page that connects while runs go on asks which** (`GET /api/runs/active`, #608) and seeds its running state from the answer, skipping runs whose end it heard meanwhile and answers to an ask a reconnect superseded; it otherwise hears of a run only from its start event, and lanes would call a running workflow done. Seeded runs have no consumed types, so the Flow's edges do not move for them (as decided for #560). Streaming previews end with their run (it failed, or its output was filtered; matched by run, since an agent may run twice in one workflow) and on a reconnect, and those kept across a refresh pass the board's filters and time range (the presets' last minutes too). An unfolded streaming card reads the artifact by ID only once it is published.
- **A run that consumed nothing** (a direct invocation, a timer) is running too; a stream goes after what its own run consumed, when an agent runs twice in a workflow.
- **A running agent that shows nothing yet gets a hatched card,** typed by what it published last (else "…"); it has nothing to unfold.
- **Cards:** two fields of the payload, or one line for a decision (the option and its probability; UNSURE hatched with the best guess; a checklist's yes count). Image thumbnails open the image viewer and do not unfold the card.
- **One card unfolds at a time,** in place, at 420 px. It shows the decision displays as they are (until the decision kit, #566), model, consumers, visibility, tags, run, time, ID, the payload and the consumption history, read by ID with `embed_meta` (#605). Esc folds what the view unfolded: the artifact on the Blackboard, the agent on the Flow.
- **No "One lane per run ▾" menu** (the mockup's): the spec has one grouping. The Lanes/Table choice is saved; the review filter is not.
- **The artifact table** reads the newest page first and pages back ("Load Older"): the store keeps artifacts oldest first, and offsets of older artifacts hold as new ones are appended. Its scroll effect rendered without end once it had rows (a new range object each time); that and the reload on every page are fixed here, also for the timeline dock's History. The same component on `main` has these bugs.
- **Removed:** the artifact detail windows (`DetailWindowContainer`, `MessageDetailWindow`, `uiStore.detailWindows`), `MessageNode` and `TransformEdge`. `MessageNode`'s decision tests moved to `ArtifactBody`. `react-rnd`, used only by the detail window, stays in `package.json` until a dependency cleanup.

### #566 Decision kit

- **The rebuild was done by a subagent from the spec and the mockup and reviewed here** (diff, tests, a fixture harness of every element in both themes, the triage demo live). Its calls, kept:
  - Probabilities read 0.52, not 52 % (the mockup).
  - The tournament bracket highlights on hover in `--text`, not amber (amber means "happening now"); its emoji are gone, the winner is marked ◆; its Close button is text.
  - The yes/no bar's chosen side is blue; an unsure answer tints yes at 45 %, as the mockup does.
  - A decider's scale columns are all blue (they count decided answers); "most often no" chips are neutral (coral is for failed only).
  - Scores keep two decimals; "+N more options, each below 1 %" stays.
  - A checklist's legend counts refused items apart from unsure ones (the mockup's legend).
- **The Blackboard's unfolded card leaves out the decision's question and kind,** since its head names them; elsewhere a decision has its header.
- **The question's instructions are not drawn:** decision views carry the question's name, not its text.
- **The review buttons' preselected best guess wins over the global `.btn` style** whichever stylesheet loads last (the live build loaded `.btn` after the module).
- **The decider's Needs review queue** comes from the graph snapshot (#610): at most 20 shown, newest first, "and N more" for the rest; each with the decided artifact's title (a field that names it), its run, the two best guesses and the review buttons; a review takes it out on the next refresh. It says where unsure answers route ("route to Route.UNSURE and wait here for a person").
- **The paid examples in `examples/15-decisions/` were not run for this PR** (they call real decision models); the kit was checked with a harness of fixture decisions for every kind and on the triage demo (choice, yes/no, review queue).

### #567 Publish composer

- **The composer was built by a subagent from the spec and the mockup and reviewed here** (diff, tests, the triage demo live in both themes). Its calls, kept:
  - The system types are a second listbox after their disclosure button (a button cannot sit inside a listbox); the arrow keys go on from one into the other, and a search opens them when it finds one.
  - Selection follows focus in the type list; ↑ on the first type returns to the search, ↓ from the search enters the list.
  - Decision types show no field count (the mockup; every decision has the same fields).
  - No type is preselected: the composer opens on the search.
  - The JSON button is off while pictures convert; JSON mode checks the schema's `required` strictly.
  - Ctrl/⌘+Enter submits through `requestSubmit()`, so it runs the same checks as the Publish button.
  - "Stop following" clears the correlation filter only while it is still that run.
- **"Follow this run on the board" is on by default,** as the mockup shows it; publishing from the dashboard is mostly to watch the run.
- **The toast is one message at a time in `uiStore`,** bottom center of the board above the timeline dock, 8 s, with one action; the next toast replaces it.
- **The moves are their own commit,** so `git log --follow` keeps the history of the composer and its tests (the rewrite is 34 % similar).
- **The shortcuts dialog only renames the entry** ("publish composer"); ⌘↵ joins it with the new keys in #569.
- **From JSON back to the form only without losses** (review): the composer round-trips the JSON through the form and stays in JSON, naming the fields, if anything would change, drop or be added. Preserving such values in the form was the alternative; the form cannot show `None`, list items with line breaks, objects, lists of objects or unknown fields.
- **While a modal dialog is open (`aria-modal`), the board's shortcuts are off except Esc** (review): Ctrl+F opened the filters behind the composer and took the focus out of it. This covers the tournament bracket and the image viewer too.
- **What an input cannot show keeps JSON mode too** (review): line breaks in a one-line text input and an option the select does not have count as losses; `inputKind` in `form.ts` is the one place that says which input a field gets.
- **On short screens (under 560 px high) the whole composer scrolls** (review): at 667 × 375 the footer was clipped; the composer is now one scroll area, the footer at its end.

### #568 ⌘K palette

- **No mockup of the palette exists:** it takes the publish composer's overlay (scrim, dialog, tokens), 640 px wide, a 15 px search, results grouped as Agents, Types, Runs, Commands.
- **One result, up to three actions:** Enter, Shift+Enter, Ctrl/⌘+Enter, and the active result's actions as buttons in the footer (a listbox option cannot hold buttons).
- **Agents: Show, Unfold, Focus.** Show selects the agent and centers the board on it at the zoom it has, and puts the keyboard focus on it. From the Blackboard the agent's actions switch to the Flow and wait until its agents are loaded and laid out.
- **Types: Filter by type replaces the type filter** with that type (show only it), it does not add to it. Publish this type opens the composer on the type.
- **Runs come from the filters' correlation list,** newest first, five without a query; a typed hex start finds the run by its full ID.
- **Commands offer what applies now:** the other view only, the time ranges but the current one, themes but the current one, "Clear filters" only with filters, the canvas commands only on the Flow, "Collapse the timeline dock" only when it is open.
- **Ranking:** prefix, word start (camelCase and snake_case split), substring, then the initials of the words (labels only); scattered letters do not match ("tri" found every theme). Groups follow their best match.
- **Ctrl+F is not caught any more** (the spec's "Where everything went"): the palette replaces it, and the browser's find works again.
- **Ctrl+K does not open the palette over another modal** (the composer, the bracket, the image viewer); from inside the palette it closes it.
- **Shortcut labels follow the platform** (`utils/keys.ts`): Ctrl+K and Ctrl+↵ on Windows and Linux, ⌘K and ⌘↵ on a Mac, in the header, the palette and the composer.
- **The canvas registers its commands** (`canvasCommands.ts`) while it is mounted; a command for an unmounted canvas waits for the next one.
- **Two fixes the palette needed:** the board's refresh kept no selection (a selected node lost it within a second), and a layout set the nodes of its render over changes made since; it now sets positions only.
- **The lanes keep showing running runs of other correlations under a correlation filter** (a bug from #565, found in the live check); it gets its own fix.
- **Unfold and Focus wait for their agent like Show** (review), and **the newest request wins** (review): a command still waiting for the Flow's board is dropped when another comes.
- **"running" next to an agent comes from the runs going on** (review): `/api/agents` reports ready or waiting, never running.
- **Ctrl+K does not open the palette over the keyboard shortcuts** (review); the shortcuts dialog becomes a real modal in #569.
- **A run from before the time range widens it to all time** when the palette filters by it or shows its lane (review); a run inside the range keeps it.
- **Leaving the Flow drops what still waits for it** (review): a Show from the Blackboard abandoned by switching back does not select the agent on a later visit.
- **Show its lane turns "Needs review only" off** and **the palette gives the focus back before an action opens another overlay** (review).

### #614 Blackboard as a graph (asked for in review of #565)

- **Lanes | Graph, no Table:** the table was the timeline dock's History, the same component; History stays in the dock. A saved "table" view opens as lanes.
- **The graph's cards are the lanes' cards** (folded and unfolded), not a second card style; arrows are `smoothstep` in `--line-2`, dashed after an unsure decision, amber and moving to a card that still streams (from what its run consumed, as the lanes place it).
- **One layout of all artifacts was unreadable** (dagre stacks 120+ small runs in one column 50 000 px tall): each run is laid out on its own and the runs are packed in rows (`packRuns`), oldest first, so new runs come at the end. The first view shows the newest row at the top, at the zoom that fits it (at most 100 %).
- **Top down is the graph's default layout:** runs are narrow trees, three or four to a row; left to right they are wide and fill a row alone.
- **Every run takes a slot as large as the largest run**, both ways: a run grows down and, as its decisions fan out, sideways; a slot only as large as the run let it grow into its neighbour.
- **Cards stay where they are:** a busy board (the demo publishes 70+ artifacts a minute) moved under the reader with every new artifact. A run that gets a card is laid out again from its slot's corner (its own cards may shift inside it), new runs take the next free slot in the last row, then a row below (`placeFresh`). Auto-arrange is off by default here and lays everything out again when on, as on the Flow.
- **Moved cards stay while the view is open; a new visit lays the board out afresh** (review): saved absolute places do not fit a board whose window of artifacts and slots change between visits (a dragged card came back beside a different layout and pulled its run around it), so the graph saves no places. The former view's `layout_blackboard_view` store stays unused.
- **The registry knows which canvas it has** (`kind: 'flow' | 'graph'`): Show agent from the graph waits for the Flow instead of running on the graph.
- **The truncation note sits in the toolbar** on the graph ("the newest 500, older ones in History"); over the canvas it covered cards.
- **A run that outgrows its slot moves to free room** (review): slots are as large as the largest run at the time; a run that grows past it and would cover a neighbour goes to the next free slot, as a new run does, rather than overlapping.
- **Edges drawn once a run finished lay their run out again** (review): the server draws a run's edges only when it is done, so its cards first stand side by side; new edges between cards on the board count as growth.
- **A change of what the board shows lays the graph out afresh** (review): after a filter (or Needs review only) the remaining cards kept their places from the full board, too far apart to fit, and the view could show none of them. Once the result is in (the snapshot for new filters), the graph is laid out again and shows its newest row; live updates keep the layout.
- **No deleting with Backspace, on the graph and on the Flow** (review on the graph; the Flow had the same default): React Flow removed the selected node from the view, not from the blackboard or the flock, until the next snapshot brought it back.
- **The expanded timeline dock fits the cards that were in view into its strip** (review): the graph keeps the Flow's viewport handling (`useDockViewport`), but fits only what the reader was looking at; all 500 cards would be specks. Collapsing gives the view back.
- **New runs go below every card when the last row's free slot is not free** (review): in a grid or a circle a taller card can reach into it.
