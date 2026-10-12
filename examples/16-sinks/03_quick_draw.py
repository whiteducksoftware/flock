"""
Sinks: Quick, Draw!

Draw on a canvas and a decision model guesses what it is, after every stroke.
The drawing goes into Flock over REST as an image, the guess comes back
through a sink, and the page shows the probabilities live until the model is
sure.

- After every stroke the page sends the canvas to the app, which uploads it
  to `POST /api/v1/artifacts/upload` as a `Sketch` (the image as a file part)
  with the drawing's ID as `correlation_id`: one drawing, one run.
- `guesser` decides a `Guess`, a Choice of 16 things, at threshold 0.6.
- The `app` sink posts every guess to the app's `/guess`, in stroke order; the
  page shows the top guesses and "Got it: sun, after 4 strokes" once the
  model is sure of what was asked for (a sure wrong guess shows, and drawing
  goes on).

The sketch goes to the model as an image, so the guesser needs a decision
model that takes images: `openai/gpt-6-luna` (`azure/decision-1` takes none).

🎯 Key Concepts:
- Images over REST: a multipart upload into an `Image` field
- `correlation_id` on an upload: one run per drawing
- "Ask again after every stroke": one publish, one decision, one delivery

🎛️  CONFIGURATION:
- `--fake`: a stand-in guesser that grows surer stroke by stroke (no API key)
- DECISION_MODEL below (OPENAI_API_KEY)
- Open http://127.0.0.1:8793 to draw and http://127.0.0.1:8344 for the dashboard
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import random
import uuid
from collections.abc import Sequence

import httpx
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from flock import Choice, Decision, Endpoint, Flock, Image, flock_type
from flock.decisions.providers import DecisionAnswer, DecisionProvider, DecisionQuestion


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
DECISION_MODEL = "openai/gpt-6-luna"
THRESHOLD = 0.6
FLOCK_PORT = 8344
APP_PORT = 8793
THINK_SECONDS = 0.3  # the stand-in's answer time (--fake)
# ============================================================================


@flock_type
class Sketch(BaseModel):
    """The drawing so far, after one more stroke."""

    drawing: str
    stroke: int
    image: Image


class Guess(Choice):
    """What does this sketch show? It is drawn quickly with a mouse, in black
    lines on white, and may be unfinished."""

    airplane = ""
    bicycle = ""
    bird = ""
    butterfly = ""
    car = ""
    cat = ""
    clock = ""
    fish = ""
    flower = ""
    guitar = ""
    hot_air_balloon = "A hot air balloon"
    house = ""
    star = ""
    sun = ""
    tree = ""
    umbrella = ""


PROMPTS = list(Guess.__options__)


# ============================================================================
# The app
# ============================================================================
drawings: dict[str, dict] = {}  # drawing -> {"prompt", "strokes", "guesses", "done"}
listeners: list[asyncio.Queue] = []
app = FastAPI()


def push(event: dict) -> None:
    for queue in listeners:
        queue.put_nowait(event)


class Stroke(BaseModel):
    drawing: str
    png: str  # the canvas as a data URL


@app.post("/drawings")
async def new_drawing():
    drawing = f"draw-{uuid.uuid4().hex[:8]}"
    drawings[drawing] = {
        "prompt": random.choice(PROMPTS),
        "strokes": 0,
        "guesses": set(),  # decisions shown, for retried deliveries
        "done": False,
    }
    return {"drawing": drawing, "prompt": drawings[drawing]["prompt"].replace("_", " ")}


@app.post("/strokes")
async def stroke(body: Stroke):
    """One more stroke: the canvas goes to Flock as a file upload, in the drawing's run."""
    state = drawings[body.drawing]
    state["strokes"] += 1
    png = base64.b64decode(body.png.split(",", 1)[1])
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://127.0.0.1:{FLOCK_PORT}/api/v1/artifacts/upload",
            data={
                "type": "Sketch",
                "payload": json.dumps({
                    "drawing": body.drawing,
                    "stroke": state["strokes"],
                }),
                "correlation_id": body.drawing,
            },
            files={"image": ("sketch.png", png, "image/png")},
        )
        response.raise_for_status()
    return {"stroke": state["strokes"]}


async def stroke_of(sketch_id: str) -> int:
    """The stroke a guess answers: its sketch, read back over Flock's REST API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://127.0.0.1:{FLOCK_PORT}/api/v1/artifacts/{sketch_id}",
            params={"images": "thumbnails"},
        )
        response.raise_for_status()
    return response.json()["payload"]["stroke"]


@app.post("/guess")
async def guess(envelope: dict):
    """The sink's delivery: one decision of `guesser`, in the drawing's run."""
    decision = envelope["payload"]
    state = drawings.get(envelope.get("correlation_id") or "")
    if state is None:
        return {"ok": False}
    if envelope["id"] in state["guesses"]:
        return {"ok": True}  # a retried delivery: shown already
    stroke = await stroke_of(decision["subject_ids"][0])
    if envelope["id"] in state["guesses"]:
        return {"ok": True}  # a retry of it was shown while this one looked up
    state["guesses"].add(envelope["id"])
    # Got it once the model is sure of what was asked for; a sure wrong guess
    # is shown, and drawing goes on
    right = decision["choice"] == state["prompt"]
    first = right and not state["done"]
    state["done"] = state["done"] or right
    push({
        "drawing": envelope["correlation_id"],
        "probabilities": decision["probabilities"],
        "choice": decision["choice"],
        "best_guess": decision.get("best_guess"),
        "strokes": stroke,
        "got_it": first,
    })
    return {"ok": True}


@app.get("/events")
async def events():
    queue: asyncio.Queue = asyncio.Queue()
    listeners.append(queue)

    async def stream():
        try:
            while True:
                yield f"data: {json.dumps(await queue.get())}\n\n"
        finally:
            listeners.remove(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
async def page():
    return PAGE


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Quick, Draw! with Flock</title>
<style>
  body { font: 15px system-ui, sans-serif; background: #0e0f11; color: #eceef1; display: flex; gap: 28px; padding: 28px; }
  canvas { background: #fff; border-radius: 10px; cursor: crosshair; touch-action: none; }
  .side { display: flex; flex-direction: column; gap: 12px; min-width: 300px; }
  /* Room for the five bars and the status line from the start: the button below keeps its place */
  #bars { min-height: calc(5 * 1.3em); }
  .bar { display: grid; grid-template-columns: 16ch 1fr 44px; gap: 10px; align-items: center; font-family: monospace; height: 1.3em; }
  .bar > span:first-child { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #status { min-height: 1.6em; white-space: nowrap; }
  .track { height: 8px; background: #23262b; border-radius: 4px; overflow: hidden; }
  .fill { display: block; height: 100%; background: #7ba8f5; }
  .got { color: #9dbef8; font-size: 18px; }
  button { font: inherit; padding: 8px 14px; border-radius: 8px; border: 1px solid #3a3e45; background: #1c1f23; color: inherit; cursor: pointer; }
</style>
<canvas id="canvas" width="480" height="480"></canvas>
<div class="side">
  <h2 style="margin:0">Quick, Draw!</h2>
  <div id="prompt"></div>
  <div id="bars"></div>
  <div id="status"></div>
  <button id="new">New drawing</button>
</div>
<script>
  const canvas = document.getElementById('canvas'), pen = canvas.getContext('2d');
  let drawing = null, down = false, shown = 0;
  pen.lineWidth = 5; pen.lineCap = 'round'; pen.lineJoin = 'round';
  function point(event) { const r = canvas.getBoundingClientRect(); return [event.clientX - r.left, event.clientY - r.top]; }
  // The canvas keeps the pointer until the stroke ends, also outside it
  canvas.onpointerdown = (event) => {
    down = true; canvas.setPointerCapture(event.pointerId); pen.beginPath(); pen.moveTo(...point(event));
  };
  canvas.onpointermove = (event) => { if (down) { pen.lineTo(...point(event)); pen.stroke(); } };
  async function end() {
    if (!down) return;
    down = false;
    await fetch('/strokes', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drawing, png: canvas.toDataURL('image/png') }) });
  }
  canvas.onpointerup = end;
  canvas.onpointercancel = end;
  async function start() {
    pen.fillStyle = '#fff'; pen.fillRect(0, 0, 480, 480);
    const response = await fetch('/drawings', { method: 'POST' });
    const created = await response.json();
    drawing = created.drawing;
    shown = 0;
    document.getElementById('prompt').innerHTML = `Draw: <b>${created.prompt}</b>`;
    document.getElementById('bars').innerHTML = '';
    document.getElementById('status').textContent = '';
  }
  const events = new EventSource('/events');
  events.onmessage = (message) => {
    const guess = JSON.parse(message.data);
    if (guess.drawing !== drawing) return;
    if (guess.got_it) {
      document.getElementById('status').innerHTML =
        `<span class="got">Got it: ${guess.choice.replace(/_/g, ' ')}, after ${guess.strokes} stroke${guess.strokes === 1 ? '' : 's'}</span>`;
    }
    // The bars show the newest stroke: a late answer for an older one changes them not
    if (guess.strokes < shown) return;
    shown = guess.strokes;
    const top = Object.entries(guess.probabilities).sort((a, b) => b[1] - a[1]).slice(0, 5);
    document.getElementById('bars').innerHTML = top.map(([option, p]) =>
      `<div class="bar"><span>${option.replace(/_/g, ' ')}</span>` +
      `<span class="track"><span class="fill" style="width:${Math.round(p * 100)}%"></span></span>` +
      `<span>${p.toFixed(2)}</span></div>`).join('');
    if (!guess.got_it && !document.getElementById('status').innerHTML.includes('Got it')) {
      document.getElementById('status').textContent = guess.choice === 'UNSURE'
        ? `Not sure yet: ${(guess.best_guess || '').replace(/_/g, ' ')}?`
        : `I see a ${guess.choice.replace(/_/g, ' ')}…`;
    }
  };
  document.getElementById('new').onclick = start;
  start();
</script>
"""


# ============================================================================
# Without a key: a stand-in that grows surer of the prompt stroke by stroke
# ============================================================================
class StrokeByStroke(DecisionProvider):
    """Knows what was asked for (the app's prompt) and grows surer with every
    stroke; a model sees only the image."""

    label = "fake/stroke-by-stroke"
    supports_images = True

    async def decide_many(
        self, state: str, questions: Sequence[DecisionQuestion], images=()
    ) -> dict[str, DecisionAnswer]:
        await asyncio.sleep(THINK_SECONDS)  # about as long as a model takes
        sketch = json.loads(state.split(": ", 1)[1])
        prompt = drawings[sketch["drawing"]]["prompt"]
        answers = {}
        for question in questions:
            sure = min(0.92, 0.12 + 0.13 * sketch["stroke"])
            others = [option for option in question.options if option != prompt]
            weights = [random.random() for _ in others]
            rest = 1 - sure
            probabilities = {
                option: rest * weight / sum(weights)
                for option, weight in zip(others, weights, strict=True)
            }
            probabilities[prompt] = sure
            choice = max(probabilities, key=probabilities.get)
            answers[question.name] = DecisionAnswer(
                choice=choice,
                probabilities=probabilities,
                confidence=probabilities[choice],
                model=self.label,
            )
        return answers


# ============================================================================
# The flock
# ============================================================================
def build_flock(fake: bool) -> Flock:
    flock = Flock(
        decision_model=StrokeByStroke() if fake else DECISION_MODEL,
        endpoints={"app": Endpoint(f"http://127.0.0.1:{APP_PORT}", retries=3)},
    )
    # One guess at a time, so the guesses come back in stroke order
    flock.agent("guesser").description("Guesses what the sketch shows").consumes(
        Sketch
    ).max_concurrency(1).decides(Guess, threshold=THRESHOLD)
    flock.sink("app").consumes(Decision.of(Guess)).post("app:/guess")
    return flock


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument(
        "--fake", action="store_true", help="a stand-in guesser, no API key"
    )
    args = parser.parse_args()

    flock = build_flock(args.fake)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=APP_PORT, log_level="warning")
    )
    asyncio.get_running_loop().create_task(server.serve())
    print(
        f"\n✏️  Draw: http://127.0.0.1:{APP_PORT}   🦆 The dashboard: http://127.0.0.1:{FLOCK_PORT}\n"
    )
    await flock.serve(dashboard=True, port=FLOCK_PORT)


if __name__ == "__main__":
    asyncio.run(main())
