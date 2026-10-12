# Making a Flock video

How the v0.5.8 feature video was made, so the next one (a vertical short, a square post, a new release) takes hours, not a day. No sound, motion graphics in the dashboard's own look (Unfold: Geist, Graphite, the amber and blue signals), real recordings of a running Flock.

```text
record (Playwright, CDP screencast)  ->  frames/<name>-raw/   JPEG per repaint + index.json
stage  (stage/index.html, stage.js)  ->  scenes over time, any aspect ratio
render (tools/render.mjs)            ->  out/frames-<name>/  ->  out/<name>.mp4 (ffmpeg)
```

`frames/` and `out/` are gitignored; a 110 s video takes about 700 MB of recordings and 400 MB of rendered frames.

## Setup

```bash
cd docs/internal/video/tools
npm install                        # Playwright, pinned in package.json
npx playwright install chromium    # or point CHROME at a Chromium build
# ffmpeg on the PATH; Node 20+; the branch to film checked out in a worktree with `uv sync`
```

The stage takes Geist from the dashboard's dependencies (`src/flock/frontend/node_modules`, SIL OFL 1.1), so run `npm install` in `src/flock/frontend` once.

## 1. Plan

Write the storyboard first: scenes, seconds, what each shows, which recording it needs. Decide with the owner before recording:

- **Format and length:** 16:9 (1920x1080) for YouTube, LinkedIn and slides; 9:16 (1080x1920) for Reels and Shorts; 1:1 (1080x1080) or 4:5 (1080x1350) for Instagram posts. 90 to 120 s for a release video, 20 to 45 s for a short.
- **Live or fake models:** live demos look real and cost a few cents (Snake on `azure/decision-1`, Quick Draw on `openai/gpt-6-luna`); everything else runs on fake models (`tools/fake_models.py`), no keys, same pictures every time.
- **The version text** (a series like `v0.5.8` stays true across patch releases).
- **Facts** with their sources, e.g. the install size and time before and after dropping torch: PR #461 (`uv sync --no-dev --extra semantic`, fresh container: 302.3 s and 7.48 GB with torch, 10.3 s and 404 MB with ONNX).

The v0.5.8 storyboard, 111 s: intro (wordmark, version) 5 s · PLAY (Snake and the Flow) 18 s · SEE (Quick, Draw! and the guesser's thumbnails) 19 s · a new dashboard (old one wiped into the new) 8 s · FLOCK CAN ALSO ... (12 features x 4 s) 50 s · FLOCK GOT LIGHTER (torch -> ONNX) 8 s · credits 6 s.

## 2. Record

Start every demo in its **own process on its own ports**, from a worktree of the branch to film:

```bash
# Live demos (keys from .env)
uv run python examples/16-sinks/02_snake.py --port 8901 --flock-port 8451
# Quick Draw has no port flags: import it, set APP_PORT / FLOCK_PORT, run main() (see record-draw.mjs)

# Feature clips: fake models, one example each
uv run python docs/internal/video/tools/fake_models.py examples/15-decisions/07_escalation.py --port 8461
# 08_voting 8462, 09_shadow 8463, 10_explain 8464, 06_control_mapping_tournament 8465,
# 05_compliance_checklist 8466, 11_coverage 8467, 13_human_review 8469
uv run python examples/04-misc/10_dashboard_triage_demo.py --port 8470
# The old dashboard, for before/after: the triage demo from a worktree of main before the rework, port 8471
```

Then, in `tools/`:

```bash
node record-snake.mjs 8901 8451 32           # frames/snake-game-raw, frames/snake-board-raw
node record-draw.mjs 8902 8452 4             # frames/draw-app-raw, frames/draw-board-raw
node record-features.mjs                     # frames/clip-<name>-raw, or name the clips to redo
```

Record two or three takes of the live scenes and keep the best (a longer Snake game, drawings that are guessed after a few strokes, not the first).

What the recorders do and why:

- **CDP screencast, not `recordVideo`.** Playwright's video is VP8 at about 1 Mbit/s: blurry UI text. The screencast gives a JPEG (quality 92) per repaint with its timestamp; `index.json` lists frames and named marks (`start`, `act`, `start:fish`) to cut on.
- **Size.** Feature clips record 1280x720 CSS pixels at device scale 1.5: 1920x1080 frames with the UI 1.5x larger than at 1080p, so it stays readable when the stage frames a part of it. Split-screen pages record at about their panel size. The screencast sends device pixels only when the browser itself runs at the page's scale, so `launch()` starts one Chromium per scale with `--force-device-scale-factor`; with the page's `deviceScaleFactor` alone a 1.5x page comes as 1280x720 frames.
- **Recording-only CSS** is fine: the Snake page is stacked into a column and its address box hidden (`addStyleTag`); nothing changes in the product.
- **Few frames are fine.** A page that does not change sends no frames; the stage holds the last one and dissolves a jump (an unfold, a scroll) over 0.3 s instead of cutting.

Gotchas we hit:

- Several servers from one worktree build the dashboard at the same time into the same `static/` and crash; start one, wait for its build, then the rest.
- **Warm up before the take**, so the Flow keeps still while it is recorded: bring every agent onto it (`external` appears with the first artifact; Snake publishes one step itself in a run of its own, Quick Draw draws one picture so the guesser's card has its thumbnails), fit it once, switch Auto-arrange off, then start recording. A fit or an auto-arrange during the take moves the whole board.
- The Blackboard shows the time range only: the examples publish slowly, so switch to the last hour (`lastHour`) before looking for a decision's lane.
- Unfolded decision cards are taller than a 720 px window: scroll the section that matters (Escalation, Vote, Shadow, Explanation) to the middle.
- `azure/decision-1` allows 100 requests per minute (`decision_rate_limit="100/min"` in the demo): Snake plays about 100 steps, then stalls until the window frees. 20 s of play is the most one take gives.
- A vision model may guess the house from its first stroke; draw every stroke anyway, so the picture is finished on screen.
- Frame times come from a monotonic clock (`record()` notes when each frame arrives). The screencast's own timestamps follow the wall clock, which on WSL steps back by about 2 s every 30 s: the stage would play those frames out of order. `check_motion.py` says when a recording's times step back.
- A board that keeps changing moves its lanes on purpose (a new run arrives on top, a stream ends and its card gets shorter): these glide. Pick the calmest seconds with `check_motion.py --calm` rather than cutting around every glide.
- Stop servers by PID (`ss -ltnp | grep :PORT`, `kill -9 PID`), never `pkill -f` with a pattern that is also in your own command line.

## 3. Stage

`stage/index.html` and `stage/stage.js` are one page that draws the video at any size: `stage/index.html?w=1080&h=1920`. `window.renderFrame(n)` sets every element for frame `n` (30 fps) and resolves once its images are decoded; nothing in it depends on wall time, so every render gives the same frames.

- **Scenes:** `scene(name, seconds, build)`; `build(root, seconds)` creates the scene's elements once and returns `update(t)` with the scene's own time. Scenes overlap by 0.5 s and crossfade; titles leave before their scene ends.
- **Format:** `SHAPE` is `wide` (wider than 1.3:1), `square` or `tall`; `U` is one unit of type and spacing (the short side / 1080); `M` the margin. `twoPanels()` puts two windows side by side unless the frame is tall, where it stacks them by shares of its height and crops them: a clip's `tall` camera (`tall: { cx, cy, zoom }`) picks what shows, e.g. the Snake canvas (`cy: 0.3`). The feature reel puts its text left of the window when wide and below it otherwise. Write every position from `W`, `H`, `U` and `M`, never in fixed pixels.
- **Windows:** `panel()` films a recording through a camera: `show(name, time, zoom, cx, cy)` centres (cx, cy) of the recording (0..1) at the given zoom over a cover fit, never past its edges. Frame each feature by its centre and zoom; push in slowly (a few percent over the clip).
- **Type:** `title(parent, 'FLOCK CAN NOW *PLAY!', size)`: words rise in one after another; `*word` is amber, `~word` blue. `chip(parent, head, sub, size)`: a small card with a line of code that slides in and out.
- **Content:** `ANCHORS` lists the feature clips (recording, verb, code, line, camera x, camera y, zoom); `VERSION` is the intro's version. Recordings are referred to by name (`snake-game`, `clip-escalate`, ...).

Preview a few moments before rendering everything, and look at them side by side:

```bash
node render.mjs --w 1920 --h 1080 --name flock-16x9 --at 2,9,14,25,34,44,53,66,75,93,103,108
# out/preview-flock-16x9/t*.png; a contact sheet:
ffmpeg -i t00009.png -i t00014.png -i t00025.png -i t00034.png -filter_complex "[0][1][2][3]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0,scale=1920:-1" sheet.png
```

## 4. Render

```bash
node render.mjs --w 1920 --h 1080 --name flock-v0.5.8-16x9 --all   # about 4 minutes for 111 s
node render.mjs --w 1080 --h 1920 --name flock-v0.5.8-9x16 --all   # Reels, Shorts
node render.mjs --w 1080 --h 1080 --name flock-v0.5.8-1x1 --all    # Instagram
node render.mjs --w 1080 --h 1350 --name flock-v0.5.8-4x5 --all    # Instagram portrait
```

Every format renders without overflow, but only 16:9 was art-directed for v0.5.8. Before shipping another format, preview every scene and tune it: on a square frame the side-by-side windows are small and the chips cover part of them (move chips above the windows, or let one window fill the frame with the other as an inset); on a tall frame wide UI such as the palette is cropped (a lower `zoom` in the anchor's camera); a short needs fewer scenes, not faster ones.

Every frame is a JPEG (quality 95) in `out/frames-<name>/`, then `ffmpeg -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -movflags +faststart` makes `out/<name>.mp4` (H.264, plays everywhere, about 20 to 40 MB). For a short, shorten the scene list (drop scenes, fewer anchors, `PER` seconds per anchor) rather than speeding things up: one idea per 3 to 4 seconds.

## 5. Review

Check every recording for motion before it goes on the stage, and the rendered frames before they go out:

```bash
uv run --with numpy --with pillow python tools/check_motion.py recording frames/clip-lanes-raw [--calm 4.5]
uv run --with numpy --with pillow python tools/check_motion.py rendered out/frames-flock-v0.5.8-16x9
```

- **Recording:** every shift of the whole frame ("moved", with its time and size) and of a part of it ("local", a 4 x 4 grid: a button pushed down by a line above it), and the shifts that turn back within two seconds ("turn-backs"). Moves in a row over 10 to 20 frames are glides; one large move in one or two frames is a jump. Local moves also find what moves on purpose (the snake, a stroke), and the first frame of a panel that appears can read as a large move: look at the frames before you call it a bug. `--calm` finds the quietest window of a long take.
- **Rendered:** a frame far from both neighbours (a jump) or unlike the frames before and after, which agree (a flicker).
- What turns out to be the product's, not the take's, goes to an issue: the v0.5.8 video found lanes that jumped while runs ended (#642), an unfold that popped (#644), demo pages whose buttons jumped (#646), layout and camera moving against each other (#648, #650) and lanes drawn over each other while a card unfolded (#652).

Then look at a contact sheet of every scene and check:

- text is readable at the target size (UI text at least about 16 px after the camera's zoom, titles inside the frame);
- titles and chips do not overlap each other or the part of a window that matters;
- every number has a source (issue, PR, changelog) and matches it;
- nothing private is in a frame: no keys, no personal paths or names, no customer data (demos only), no personal photos;
- the scenes run in order and no window is cut off at a format's edge (render previews of every format you ship).
