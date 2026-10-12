# Flock dashboard design system: "Unfold"

The design for the dashboard rework, approved on 2026-10-11. It is built on the `ui-rework` branch; `main` keeps the current dashboard until the rework is complete. The work is split into the issues of the epic [#557](https://github.com/whiteducksoftware/flock/issues/557) (#558–#569); each gets a branch from `ui-rework` and a PR into `ui-rework`. For the rework it supersedes `src/flock/frontend/docs/DESIGN_SYSTEM.md`, which still describes the dashboard on `main`.

- **Tokens:** [`tokens.css`](tokens.css), both themes, ready to drop into `src/flock/frontend/src/styles/`.
- **Mockups:** [`mockups/`](mockups/), the sources of the eight artboards of the design canvas (see [Mockups](#mockups)). Exact paddings, sizes and copy come from there.
- This folder lives under `docs/internal/`, which `mkdocs.yml` excludes from the docs site, and outside `src/`, so it is not packaged into the wheel.

## Principles

1. **Everything about a node lives in the node.** There is no context menu, no floating detail window and no module hidden behind a right click. A node unfolds on the board to show its live output, history, runs and traces, and opens into focus for more room.
2. **Color only ever means something.** Four signals (below) carry all the color. Everything else is graphite or paper.
3. **Structure comes from position, weight and type.** Inputs sit left, outputs right. Colored left-border callouts, glows and gradients are gone.
4. **Types are the contract.** Type names, IDs and numbers are set in the mono face, without the module prefix: `SupportTicket`, not `__main__.SupportTicket`. The full path is in the tooltip.
5. **Quiet when idle.** When nothing runs, there is no amber on screen. No emoji anywhere in the interface.

## The four signals

| Signal | Token | Means | Used for |
|---|---|---|---|
| Amber | `--signal` | Happening now | Running agents (pulsing dot, card border), artifacts in flight (animated edge), streaming text, countdowns, "now" on the timeline |
| Blue | `--sure` | Decided | The option a decision chose above its threshold, `◆` handles, edges of decision options, the review option that is the best guess |
| Hatch | `.hatch` | Not sure yet | `UNSURE` answers, joins and batches still waiting, outputs still streaming, refused or missing items |
| Coral | `--error` | Failed | Agent errors and workflow errors, always with an icon or text |

The hatch is a texture, not a color, so it reads in every theme and for color-blind eyes. Blue and amber differ in lightness as well as hue.

## Tokens

All values are in [`tokens.css`](tokens.css). The root element carries `data-theme="graphite"` (default) or `data-theme="paper"`.

| Token | Graphite | Paper | Role |
|---|---|---|---|
| `--bg` | `#0B0C0E` | `#F3F2EE` | App ground, header, docks |
| `--board` | `#0D0F12` | `#F6F5F1` | Canvas behind the graph |
| `--dot` | white 6 % | black 8 % | Canvas dot grid (22 px) |
| `--surface` | `#15171B` | `#FFFFFF` | Nodes, cards, dialogs |
| `--surface-2` | `#1B1E23` | `#F5F4F0` | Buttons, inputs, nested cards |
| `--surface-3` | `#24282E` | `#EAE8E2` | Hover, selected segment, bar tracks |
| `--line` / `--line-2` | white 7.5 % / 14 % | black 8 % / 15 % | Dividers / borders |
| `--text` | `#ECEEF1` | `#16171A` | Primary text |
| `--text-2` | `#B0B6BF` | `#4A4F57` | Secondary text |
| `--text-3` | `#858C96` | `#676C74` | Labels, metadata (≥ 4.5:1 on surface) |
| `--invert` / `--on-invert` | `#ECEEF1` / `#0B0C0E` | `#16171A` / `#FFFFFF` | Primary button |
| `--signal` / `--signal-ink` | `#F2A33A` / `#F6B860` | `#D9861A` / `#9A5A06` | Amber fill / amber text |
| `--sure` / `--sure-ink` | `#7BA8F5` / `#9DBEF8` | `#2E6BD1` / `#2559B0` | Blue fill / blue text |
| `--error` / `--error-ink` | `#F07563` / `#F59384` | `#C8432F` / `#A8361F` | Coral fill / coral text |
| `--hatch` | white 22 % | black 24 % | Stripe color of `.hatch` |
| `--on-signal` / `--on-sure` / `--on-error` | `#0B0C0E` (all three) | `#16171A` / `#FFFFFF` / `#FFFFFF` | Text on a solid signal fill (filled badges and buttons) |

The `-soft` variants (13-16 % alpha) tint backgrounds such as the streaming ticker or a selected review option.

**Radii:** 6 px tags, 7-8 px buttons and chips, 10-12 px nodes and cards, 16 px dialogs. **Spacing:** 4 px base; node padding 12 × 14 px; panel padding 16-20 px; 80 px between columns of nodes in the hierarchical layout.

**Terminal themes.** The 336 themes in `src/flock/themes` keep working: the theme applicator maps them onto these tokens (background → `--bg`/`--board`, foreground → `--text`, bright black → `--text-3`, yellow → `--signal`, blue → `--sure`, red → `--error`; surfaces and lines are mixed from background and foreground). No component may hard-code a color. Text tokens of a terminal theme are checked for 4.5:1 against `--surface` and darkened or lightened when they fail; the `--on-*` tokens take the theme's background or foreground, or black or white, whichever reads on their fill.

## Typography

[Geist and Geist Mono](https://vercel.com/font) (SIL Open Font License), bundled with the frontend so the dashboard works offline. Fallbacks: `ui-sans-serif, system-ui` and `ui-monospace, SFMono-Regular, Menlo`.

| Use | Size / weight |
|---|---|
| Focus title | 20 / 600, letter-spacing −0.015em |
| Unfolded node name | 15 / 600 |
| Node name | 13.5 / 600 |
| Body | 13 / 400 |
| Secondary text | 12-12.5 / 400 |
| Mono metadata (types, IDs, counts, times) | 11-12.5 / 400-500, tabular numbers |
| Section labels | 10.5 / 500, uppercase, letter-spacing 0.07em |

## Icons

One line-icon set on a 24 px grid, 1.8 px stroke, round caps, `currentColor`. The mockups draw them inline: publish (plus), search, fold, focus, layout, history, traces, scheduled (clock), join, batch, settings, shortcuts (keyboard), error, close, chevrons. `◆` stays the decision glyph, as in Flock's API. Every icon-only button has an `aria-label`.

## Layout

```
┌ Header ── wordmark · Flow | Blackboard · scope chips · ⌘K search · Live status · Publish · settings · shortcuts ┐
│                                                                                                    minimap │
│  Board (graph or lanes)                                                                                    │
│                                                                                                            │
│  [canvas dock: − 100% + · fit · layout ▾ · auto-arrange]                                                   │
└ Timeline dock ── Activity · histogram with time brush · History · Traces · expand ─────────────────────────┘
```

Overlays: Focus (a node on a full stage), Publish composer, ⌘K palette, Settings, shortcuts dialog, tournament bracket, image viewer.

### Where everything went

Nothing the current dashboard does is dropped silently; the table maps every feature to its new home.

| Current dashboard | Rework |
|---|---|
| Title "🦆🐓 Flock 🐤🐧" | Wordmark with the flock mark (three chevrons, the lead one amber) |
| View toggle Agent View / Blackboard View, Ctrl+M | Segmented control **Flow / Blackboard**, Ctrl+M |
| Publish panel (right, open on first load), Ctrl+Shift+P | **Publish composer** (modal, closed by default), Ctrl+Shift+P |
| Agent Details button: open a window for every agent, Ctrl+Shift+D | Nodes **unfold in place**; Ctrl+Shift+D unfolds or folds the selected node ([decisions](#decisions)) |
| Settings panel, Ctrl+, | Settings sheet, Ctrl+, |
| Shortcuts dialog, Ctrl+/ | Shortcuts dialog (keyboard icon), Ctrl+/ |
| Trash button "Clear all dashboard data" | Settings › Advanced |
| Connection badge | **Live** status in the header (Live · Reconnecting (n) · Offline) plus a banner on the board while offline |
| Filter pills bar and filter flyout (Ctrl+Shift+F): presets, correlation, time range, types, producers, tags, visibility | **Scope chips** in the header: the time chip, one chip per active filter, and **+ Filter** with all facets and saved presets |
| Time range buttons | Time chip plus the **brush** on the timeline histogram |
| Ctrl+F (correlation input, only with the flyout open) | **⌘K** search over agents, types and runs (correlation IDs) |
| Right-click menu › Auto Layout ▸ hierarchical (vertical/horizontal), circular, grid, random, auto layout on/off | **Canvas dock** › layout menu and **Auto-arrange** switch |
| Right-click menu › Auto Zoom | Canvas dock › fit |
| Right-click menu › Add Module › Trace Viewer | **Timeline dock › Traces** (and the Traces tab of a node) |
| Right-click menu › Add Module › Historical Blackboard | **Timeline dock › History** (the Blackboard's alternative view is the **Graph**, #614) |
| React Flow controls (zoom, fit, lock) | Canvas dock |
| Minimap (bottom right) | Minimap (top right), token colors |
| Agent detail window › Live Output / Message History / Run Status | Unfolded node › **Live / History / Runs**, plus **Overview** and **Traces**; more room in **Focus** |
| Artifact detail window (metadata, payload, consumption history) | The artifact card **unfolds in place** in the Blackboard view; it loads the artifact by ID |
| Trace viewer tabs Timeline / Statistics / RED Metrics / Dependencies / Configuration / Guide | Dock tabs **Traces** (list, waterfall, span detail) / **Metrics** (RED and dependencies) / **Tracing settings**; the guide becomes a link to the tracing docs |
| Tournament bracket modal, image viewer modal | Stay full-screen modals, on the tokens |
| Theme selector (336 themes, live preview on hover) | Settings › Appearance: Graphite, Paper and the terminal themes; a hover previews, leaving puts the theme back |
| Agent colors, node shadow, status pulse, compact view (Appearance) | Status colors are the signals; compact view becomes the chip level; pulse respects reduced motion |
| Edge type, width, animation, labels (Graph settings) | Kept in Settings › Graph |
| Layout direction, node and rank spacing (Advanced) | Node and rank spacing kept in Settings › Advanced (they lay the Flow out again); the direction is the canvas dock's layout menu (#569) |

## Nodes: four levels

| Level | Trigger | Shows |
|---|---|---|
| **Chip** | Zoomed out, or while the timeline dock is expanded | Status dot, name, one count |
| **Card** | Default | Header (status dot, name, engine tag), input rows left, output rows right, counts; decision summary for deciders |
| **Unfolded** | Click or Space on a card; fold button or Space folds it back | Card header plus description, model, ports, and tabs **Overview · Live · History · Runs · Traces**. About 560 × 470 px. Neighbors make room: the layout reruns with the unfolded size and positions animate (200 ms) |
| **Focus** | Focus button or double-click; Esc returns | Full stage over the dimmed board: header, **lineage strip** (upstream → node → downstream, each a link), tabs **Live · History · Runs · Contract · Traces** |

### Card anatomy

- Header: 8 px status dot, name (13.5/600), an engine tag on the right: `LLM`, `OpenClaw`, `source` (the external publisher), `◆ Route` for deciders, or a clock tag with the schedule (`every 30s`, `0 9 * * 1-5`). Event-driven agents get no badge; that is the default.
- Port rows, 26 px: `IN` / `OUT` / `AND` / `JOIN` label (10 px uppercase), type in mono, count right-aligned. Rows of subscriptions without traffic show 0. A row flashes its count (not its background) when it changes.
- Handles: 9 px circles on the left and right edge.

### States

| State | Treatment |
|---|---|
| Idle | Neutral dot |
| Running | Amber pulsing dot, amber border at 55 %; LLM agents show a one-line **ticker** of the latest tokens with a blinking caret |
| Failed | Coral dot and border at 65 %, a row with icon, error type and time; click opens its trace |
| Scheduled | Clock tag, "next in …" countdown, run number and last run |
| Join waiting | Dashed box: join icon, key (`by ticket_id · 9c34`), expiry countdown (amber below 30 s), progress bar with the missing part hatched |
| Batch collecting | Dashed box: `batch 3 / 5`, timeout countdown, one cell per item, missing cells hatched |
| Decider | Distribution per question (see the decision kit); `UNSURE` is the hatched segment |

### Edges

| Edge | Treatment |
|---|---|
| Artifact flow | 1.5 px `--line-2`, label `SupportTicket · 8` in mono |
| In flight | Amber, dashed 3/7, animated |
| Decision option | Neutral line, label `◆ billing · 3` |
| `UNSURE` route | Dotted line, dashed label with a hatch swatch |
| Join or batch pending | Dashed 8/6 in `--text-3`, label with key or progress |

## Blackboard view

- **Lanes:** one lane per run (correlation ID), newest on top. The lane header shows status (running / needs review / done with duration and artifact count), run ID, the first artifact's title and time. Artifacts follow left to right, connected by arrows; decisions of one subject stack in one column.
- **Artifact card:** type in mono, producer, two key/value rows of the payload (no JSON tree), or the decision body for decisions. Clicking unfolds the card in place: full probabilities with threshold ticks, review buttons, model, consumers, visibility, ID, the payload as JSON, the consumption history.
- **Graph:** the same artifacts as cards on a canvas, arrows from what a run consumed to what it published (an arrow in flight to a card that still streams). Each run is laid out on its own (top down by default) in a slot as large as the largest run; the runs fill rows, oldest first, the first view shows the newest row. Placed cards stay where they are: a run that grows is laid out again in its slot (one that outgrows it moves to free room), new runs take the next free slot; moved cards stay while the view is open. The canvas dock lays it out again (auto-arrange off by default). The historical table is the timeline dock's History (#614).
- **Needs review only** narrows the view to runs with an unreviewed `UNSURE` decision.

## Decision kit

| Element | Encoding |
|---|---|
| Choice | Bars sorted by probability, a 2 px threshold tick on every bar; chosen option blue with a check; best guess of an `UNSURE` answer hatched with a dashed outline; the rest neutral; top 8, then "+N more" |
| Yes / No | One bar: yes from the left, no from the right, the unsure zone between 1 − t and t hatched, a marker at p |
| Scale | One column per level, the chosen level blue, a dashed threshold line, the weighted score in text |
| Checklist | One 14 px cell per item: blue yes, neutral no, hatched unsure, dashed refused; legend with counts; failed checklists say which required items are no |
| Escalation | Chips per tier: hatched for tiers that were unsure, blue for the tier that answered |
| Vote | Chip per model (blue agrees, hatched unsure, outlined differs) and the result |
| Shadow | Dashed chip with the candidate's answer, agreement so far |
| Review | Option buttons (best guess preselected in blue); afterwards "after review: ◆ option by reviewer" |
| Explanation | Text, then "Would settle it: …" |
| Tournament | Round chips (`240 options → 12 groups → 36 → …`) and an "Open bracket" button for the full-screen bracket |
| Coverage | Checklist cells per group and "combine of N documents" |
| Image lanes | Thumbnails per option on the decider, `UNSURE` lane hatched, 3× zoom with probability on hover |

The decider's **Overview** tab holds the distribution and a **Needs review** queue: each unsure decision with its best guesses and review buttons.

## Overlays

- **Publish composer:** type list on the left (search; "Your types", "Decisions", collapsed "System types"), on the right the type's docstring, a form generated from the schema (all current field kinds: images, booleans, lists, numbers, enums, long and short strings) with a **Form / JSON** switch, a **Picked up by** preview of the agents subscribed to the type, "Follow this run on the board" (sets the correlation filter), Publish with ⌘↵.
- **⌘K:** search agents, types and runs; run commands (switch view, layout modes, fit, publish, settings, shortcuts, clear filters).
- **Settings:** Graph, Appearance, Advanced, as listed in the table above.

## Accessibility

- Real `<button>`, `<a>`, `<input>` with `<label>`; icon-only buttons have an `aria-label`; tabs use `role="tab"` and `aria-selected`.
- Focus ring: 2 px `--sure`, offset 2 px, on `:focus-visible`.
- Text contrast at least 4.5:1 (3:1 from 24 px), checked for every terminal theme.
- Uncertainty is a texture, failure always has an icon or text; nothing depends on hue alone.
- `prefers-reduced-motion` stops the pulse, the flow animation, the caret and the sweep.
- Keyboard: Tab moves through nodes, Space unfolds and folds, Enter opens focus, Esc closes the top overlay, then folds, then clears the selection.

## Mockups

The eight artboards of the design canvas. Each `.dc.html` file is a self-contained page in the canvas's component format: plain HTML and inline styles, `{{name}}` placeholders filled by the small script at the end, `<sc-if>` / `<sc-for>` for tabs and repeats. They do not render on their own (the canvas runtime `support.js` is not included); read them as the reference for markup, sizes and copy. `canvas.json` is the canvas index with the artboard positions.

| File | Shows |
|---|---|
| `Main.dc.html` | Flow view: the `triage` decider unfolded on the board (tabs work), canvas dock, minimap, collapsed timeline dock |
| `Focus.dc.html` | `billing_team` in focus while it streams a reply: lineage strip, Live, History, Runs, Contract |
| `Blackboard.dc.html` | Lanes per run, one decision card unfolded with review buttons |
| `Dock.dc.html` | Timeline dock expanded over a graph of chips: Traces, History, Metrics, Tracing settings |
| `Publish.dc.html` | Publish composer with Form / JSON switch and the "Picked up by" preview |
| `Foundations.dc.html` | Four signals, both palettes, type, icons |
| `States.dc.html` | The four node levels, all agent states, board states (empty, offline), edges |
| `Decisions.dc.html` | Question types and the advanced decision elements |

The data in the mockups comes from a ticket-triage flock (`triage` decides `Route`, `urgency` decides `Urgent`, four teams answer, `pager` handles urgent tech tickets).

## Decisions

The open questions of the design review, settled on 2026-10-11:

1. **Ctrl+Shift+D** unfolds or folds the selected node.
2. **Debug mode and performance mode** (Settings › Advanced) are removed; they were stored but read nowhere.
3. **Activity histogram:** a backend endpoint returns counts per time bucket for the current filters. Bucketing on the client would be wrong for busy time ranges, since the graph loads at most the newest 500 artifacts. It lands on `main` as its own PR.
4. **Fonts:** `@fontsource-variable/geist` and `@fontsource-variable/geist-mono` (OFL-1.1), bundled with the frontend.
5. **Icons:** the inline SVGs of the mockups, as React components; no icon library.

Also decided:

- **Tokens and cost per run** (Focus › Runs, Overview) are required. The backend records LiteLLM usage per run and counts the usage that decision providers report; cost comes from LiteLLM's price table, with configurable prices for models it does not know. This lands on `main` as its own PR, before item 4.
- **A demo flock** matching the mockups (ticket triage, `FakeDecider`, a scripted streaming engine, no API keys) produces every state shown here, for screenshots and the A/B comparison. It lands on `main` as its own PR.
- **CI** runs on pull requests into `ui-rework`.
- **Screenshots** of each PR, in both themes, go into `screenshots/` in this folder; they are removed before `ui-rework` merges into `main`.
