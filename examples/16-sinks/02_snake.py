"""
Sinks: A Self-Playing Snake

A game server publishes every step over REST, a decision model picks the
snake's next move, and a sink posts the move back to the game, which steps and
publishes the next step. One decision per step, until the snake dies.

- The game publishes `SnakeState` to `POST /api/v1/artifacts` with the game's
  ID as `correlation_id`: every game is one run, one lane on the dashboard.
- `player` decides a `Move` (left, up or right, relative to the heading).
- The `game` sink posts every decision to the game's `/move`; it keeps the
  order per game, so moves arrive in the order they were decided.
- The game page draws the board and the model's probabilities live
  (server-sent events) and counts the food and the steps. Start, Pause and
  Resume hold the game between two steps.

The model gets what each move leads to, as text (`azure/decision-1` takes no
images): a wall, the snake's body, the food, or an empty cell and how far the
food is from there. The game draws the board itself.

🎯 Key Concepts:
- An app over REST into Flock and back through a sink
- `correlation_id` on a REST publish: one run per game
- Ordered delivery per correlation: the game gets every move in order
- Long runs on the dashboard: a game of 100+ steps is one lane

🎛️  CONFIGURATION:
- `--fake`: a heuristic plays instead of a model (no API key; for CI and screenshots)
- `--port` (8792) and `--flock-port` (8344): where the game and Flock run; the
  page's Flock field points the game at another Flock while it runs
- DEFAULT_DECISION_MODEL, else `azure/decision-1` (AZURE_API_BASE, AZURE_API_KEY)
- Open http://127.0.0.1:8792 for the game and http://127.0.0.1:8344 for the dashboard
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import uuid
from collections.abc import Sequence

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from flock import Choice, Decision, Endpoint, Flock, flock_type
from flock.decisions.providers import DecisionAnswer, DecisionProvider, DecisionQuestion


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
DECISION_MODEL = os.getenv("DEFAULT_DECISION_MODEL", "azure/decision-1")
SIZE = 10
FLOCK_PORT = 8344
GAME_PORT = 8792
MAX_HUNGRY = 4 * SIZE * SIZE  # steps without food before the snake starves
THINK_SECONDS = 0.15  # the stand-in's answer time (--fake)
# ============================================================================

HEADINGS = ["north", "east", "south", "west"]  # clockwise
STEP = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
TURN = {"left": -1, "up": 0, "right": 1}


@flock_type
class SnakeState(BaseModel):
    """One step of a game, as the model sees it: what each move leads to.

    The board itself stays with the game, which draws it; with the whole board
    in its state the decision model kept turning left.
    """

    game: str
    step: int
    eaten: int
    heading: str
    moves: dict[str, str]


class Move(Choice):
    """Which move keeps the snake alive and brings it closer to the food?
    `moves` says what each move leads to: a wall or the snake's own body ends
    the game, the food is best, else how far the food is afterwards. Moves are
    relative to the snake's heading."""

    left = "Turn left"
    up = "Keep the heading"
    right = "Turn right"


# ============================================================================
# The game
# ============================================================================
class Game:
    def __init__(self) -> None:
        self.id = f"snake-{uuid.uuid4().hex[:8]}"
        middle = SIZE // 2
        self.snake = [(middle, middle), (middle - 1, middle), (middle - 2, middle)]
        self.heading = "east"
        self.step = 0
        self.eaten = 0
        self.alive = True
        self.applied: set[str] = set()  # decisions already played (sink retries)
        self.paused = False
        self.waiting = False  # the next step is ready, held while paused
        self.hungry = 0  # steps since the last food
        self.food = self._place_food()

    def _place_food(self) -> tuple[int, int]:
        free = [
            (x, y) for x in range(SIZE) for y in range(SIZE) if (x, y) not in self.snake
        ]
        return random.choice(free)

    def _target(self, move: str) -> tuple[str, tuple[int, int]]:
        heading = HEADINGS[(HEADINGS.index(self.heading) + TURN[move]) % 4]
        dx, dy = STEP[heading]
        head = self.snake[0]
        return heading, (head[0] + dx, head[1] + dy)

    def _blocked(self, cell: tuple[int, int], eats: bool) -> str | None:
        if not (0 <= cell[0] < SIZE and 0 <= cell[1] < SIZE):
            return "wall"
        # The tail moves on unless the snake grows
        body = self.snake if eats else self.snake[:-1]
        return "body" if cell in body else None

    def moves(self) -> dict[str, str]:
        """What each move leads to, for the model."""
        described = {}
        for move in TURN:
            _, cell = self._target(move)
            eats = cell == self.food
            blocked = self._blocked(cell, eats)
            if blocked:
                described[move] = blocked
            elif eats:
                described[move] = "food"
            else:
                distance = abs(cell[0] - self.food[0]) + abs(cell[1] - self.food[1])
                described[move] = f"empty, food {distance} away"
        return described

    def apply(self, move: str) -> None:
        heading, cell = self._target(move)
        eats = cell == self.food
        if self._blocked(cell, eats):
            self.alive = False
            return
        self.heading = heading
        self.snake.insert(0, cell)
        self.step += 1
        if eats:
            self.eaten += 1
            self.hungry = 0
            if len(self.snake) == SIZE * SIZE:
                self.alive = False  # the board is full: won
                return
            self.food = self._place_food()
        else:
            self.snake.pop()
            self.hungry += 1
            # A snake that only circles would play forever
            if self.hungry > MAX_HUNGRY:
                self.alive = False

    def state(self) -> SnakeState:
        return SnakeState(
            game=self.id,
            step=self.step,
            eaten=self.eaten,
            heading=self.heading,
            moves=self.moves(),
        )


games: dict[str, Game] = {}
listeners: list[asyncio.Queue] = []
# Where the game publishes its steps; the page can point it elsewhere
settings = {"flock_url": f"http://127.0.0.1:{FLOCK_PORT}"}
app = FastAPI()


def push(event: dict) -> None:
    for queue in listeners:
        queue.put_nowait(event)


async def publish(game: Game) -> None:
    """The next step, over Flock's REST API, in the game's run."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings['flock_url']}/api/v1/artifacts",
            json={
                "type": "SnakeState",
                "payload": game.state().model_dump(),
                "correlation_id": game.id,
            },
        )
        response.raise_for_status()


def view(game: Game, decision: dict | None = None) -> dict:
    return {
        "game": game.id,
        "snake": game.snake,
        "food": game.food,
        "step": game.step,
        "eaten": game.eaten,
        "alive": game.alive,
        "paused": game.paused,
        "probabilities": (decision or {}).get("probabilities"),
        "move": (decision or {}).get("move"),
    }


async def advance(game: Game) -> None:
    """Publish the next step, or hold it while the game is paused."""
    game.waiting = True
    if game.paused:
        return
    await publish(game)  # a failed publish keeps the step waiting, to retry
    game.waiting = False


@app.post("/games")
async def new_game():
    game = Game()
    games[game.id] = game
    push(view(game))
    try:
        await publish(game)
    except httpx.HTTPError as exc:
        game.alive = False
        push(view(game))  # the page drops the game it never got
        raise HTTPException(
            502,
            f"Flock is not reachable at {settings['flock_url']} ({type(exc).__name__})",
        ) from None
    return {"game": game.id}


@app.post("/games/{game_id}/pause")
async def pause(game_id: str):
    game = games[game_id]
    game.paused = True
    push(view(game))
    return {"paused": True}


@app.post("/games/{game_id}/resume")
async def resume(game_id: str):
    game = games[game_id]
    game.paused = False
    push(view(game))
    if game.alive and game.waiting:
        try:
            await advance(game)
        except httpx.HTTPError as exc:
            # Paused again, its step still waiting: Resume retries it
            game.paused = True
            push(view(game))
            raise HTTPException(
                502,
                f"Flock is not reachable at {settings['flock_url']} ({type(exc).__name__})",
            ) from None
    return {"paused": False}


class Settings(BaseModel):
    flock_url: str


@app.get("/settings")
async def get_settings():
    return settings


@app.post("/settings")
async def set_settings(body: Settings):
    url = body.flock_url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Flock's address starts with http:// or https://")
    settings["flock_url"] = url
    return settings


@app.post("/move")
async def move(envelope: dict):
    """The sink's delivery: one decision of `player`, in the game's run."""
    decision = envelope["payload"]
    game = games.get(envelope.get("correlation_id") or "")
    if game is None:
        return {"ok": False}
    # A retried delivery (the next step's publish failed) plays no second
    # move: it only publishes the step again
    if envelope["id"] not in game.applied:
        if not game.alive:
            return {"ok": False}
        game.applied.add(envelope["id"])
        # An unsure decision still moves: its best guess
        chosen = (
            decision["choice"]
            if decision["choice"] in TURN
            else decision.get("best_guess")
        )
        game.apply(chosen or "up")
        push(view(game, {"probabilities": decision["probabilities"], "move": chosen}))
    if game.alive:
        await advance(game)
    return {"ok": True}


@app.get("/events")
async def events():
    queue: asyncio.Queue = asyncio.Queue()
    listeners.append(queue)

    async def stream():
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            listeners.remove(queue)

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/", response_class=HTMLResponse)
async def page():
    return PAGE.replace("{SIZE}", str(SIZE))


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Flock plays Snake</title>
<style>
  body { font: 15px system-ui, sans-serif; background: #0e0f11; color: #eceef1; display: flex; gap: 28px; padding: 28px; }
  canvas { background: #16181b; border-radius: 10px; }
  .side { display: flex; flex-direction: column; gap: 14px; min-width: 260px; }
  .bar { display: grid; grid-template-columns: 56px 1fr 44px; gap: 10px; align-items: center; font-family: monospace; }
  .track { height: 8px; background: #23262b; border-radius: 4px; overflow: hidden; }
  .fill { height: 100%; background: #7ba8f5; }
  .chosen { color: #9dbef8; }
  .over { color: #f59384; }
  .buttons { display: flex; gap: 10px; }
  .buttons button { flex: 1; }
  button, input { font: inherit; padding: 8px 14px; border-radius: 8px; border: 1px solid #3a3e45; background: #1c1f23; color: inherit; }
  button { cursor: pointer; }
  label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #b0b6bf; }
  input { font-family: monospace; font-size: 13px; }
  .hint { font-size: 12px; color: #858c96; }
</style>
<canvas id="board" width="420" height="420"></canvas>
<div class="side">
  <h2 style="margin:0">Flock plays Snake</h2>
  <div id="stats">Press Start to play.</div>
  <div id="bars"></div>
  <div id="status"></div>
  <div class="buttons">
    <button id="toggle">Start</button>
    <button id="new">New game</button>
  </div>
  <label>Flock
    <input id="flock" spellcheck="false">
  </label>
  <div class="hint" id="hint">Where the game publishes its steps (Flock's REST API).</div>
</div>
<script>
  const size = {SIZE}, cell = 42;
  const board = document.getElementById('board').getContext('2d');
  let current = null, alive = false, paused = false;
  const toggle = document.getElementById('toggle');
  function buttons() { toggle.textContent = alive && !paused ? 'Pause' : alive ? 'Resume' : 'Start'; }
  function draw(state) {
    board.clearRect(0, 0, 420, 420);
    board.fillStyle = '#f07563';
    board.beginPath();
    board.arc(state.food[0] * cell + cell / 2, state.food[1] * cell + cell / 2, cell / 3, 0, 2 * Math.PI);
    board.fill();
    state.snake.forEach(([x, y], i) => {
      board.fillStyle = i === 0 ? '#f2a33a' : '#c5852f';
      board.fillRect(x * cell + 3, y * cell + 3, cell - 6, cell - 6);
    });
  }
  function bars(probabilities, move) {
    const rows = Object.entries(probabilities || {}).map(([option, p]) =>
      `<div class="bar ${option === move ? 'chosen' : ''}"><span>${option}</span>` +
      `<span class="track"><span class="fill" style="display:block;width:${Math.round(p * 100)}%"></span></span>` +
      `<span>${p.toFixed(2)}</span></div>`);
    document.getElementById('bars').innerHTML = rows.join('');
  }
  const events = new EventSource('/events');
  events.onmessage = (message) => {
    const state = JSON.parse(message.data);
    if (current && state.game !== current) return;
    current = state.game;
    alive = state.alive; paused = state.paused; buttons();
    draw(state);
    bars(state.probabilities, state.move);
    document.getElementById('stats').textContent = `${state.game} · step ${state.step} · food ${state.eaten}`;
    document.getElementById('status').innerHTML = !state.alive
      ? `<span class="over">Game over: ${state.eaten} food in ${state.step} steps</span>`
      : state.paused ? 'Paused' : '';
  };
  async function start() {
    current = null;
    const response = await fetch('/games', { method: 'POST' });
    const answer = await response.json();
    if (!response.ok) {
      current = null; alive = false; buttons();
      document.getElementById('status').innerHTML = `<span class="over">${answer.detail}</span>`;
      return;
    }
    current = answer.game;
  }
  toggle.onclick = async () => {
    if (!current || !alive) return start();
    const response = await fetch(`/games/${current}/${paused ? 'resume' : 'pause'}`, { method: 'POST' });
    if (!response.ok) {
      document.getElementById('status').innerHTML = `<span class="over">${(await response.json()).detail}</span>`;
    }
  };
  document.getElementById('new').onclick = start;
  // Flock's address: shown from the game's settings, saved on Enter or when the field is left
  const flock = document.getElementById('flock'), hint = document.getElementById('hint');
  fetch('/settings').then((r) => r.json()).then((s) => { flock.value = s.flock_url; });
  async function save() {
    const response = await fetch('/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ flock_url: flock.value }) });
    const answer = await response.json();
    hint.innerHTML = response.ok
      ? `Publishing to ${answer.flock_url} · <a href="${answer.flock_url}" target="_blank" style="color:#9dbef8">dashboard</a>`
      : `<span class="over">${answer.detail}</span>`;
  }
  flock.onchange = save;
</script>
"""


# ============================================================================
# Without a key: a heuristic that moves safely toward the food
# ============================================================================
class SnakeHeuristic(DecisionProvider):
    """Plays from the state's `moves`: food first, then the nearest empty cell."""

    label = "fake/snake-heuristic"

    async def decide_many(
        self, state: str, questions: Sequence[DecisionQuestion], images=()
    ) -> dict[str, DecisionAnswer]:
        await asyncio.sleep(THINK_SECONDS)  # about as long as a model takes
        moves = json.loads(state.split(": ", 1)[1])["moves"]

        def score(described: str) -> float:
            if described == "food":
                return 4.0
            if not described.startswith("empty"):
                return -6.0
            distance = int(described.rsplit(" ", 2)[-2])
            return 2.0 - distance * 0.25 + random.uniform(0, 0.4)

        weights = {
            move: math.exp(2 * score(described)) for move, described in moves.items()
        }
        total = sum(weights.values())
        probabilities = {move: weight / total for move, weight in weights.items()}
        choice = max(probabilities, key=probabilities.get)
        return {
            question.name: DecisionAnswer(
                choice=choice,
                probabilities=probabilities,
                confidence=probabilities[choice],
                model=self.label,
            )
            for question in questions
        }


# ============================================================================
# The flock
# ============================================================================
def build_flock(fake: bool, game_port: int = GAME_PORT) -> Flock:
    flock = Flock(
        decision_model=SnakeHeuristic() if fake else DECISION_MODEL,
        decision_rate_limit=None if fake else "100/min",
        endpoints={"game": Endpoint(f"http://127.0.0.1:{game_port}", retries=3)},
    )
    flock.agent("player").description("Picks the snake's next move").consumes(
        SnakeState
    ).decides(Move, threshold=0.4)
    flock.sink("game").consumes(Decision.of(Move)).post("game:/move")
    return flock


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument(
        "--fake", action="store_true", help="a heuristic plays, no API key"
    )
    parser.add_argument("--port", type=int, default=GAME_PORT, help="the game's port")
    parser.add_argument(
        "--flock-port",
        type=int,
        default=FLOCK_PORT,
        help="Flock's port (API and dashboard)",
    )
    args = parser.parse_args()

    settings["flock_url"] = f"http://127.0.0.1:{args.flock_port}"
    flock = build_flock(args.fake, game_port=args.port)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=args.port, log_level="warning")
    )
    asyncio.get_running_loop().create_task(server.serve())
    print(
        f"\n🐍 The game: http://127.0.0.1:{args.port}   "
        f"🦆 The dashboard: http://127.0.0.1:{args.flock_port}\n"
    )
    await flock.serve(dashboard=True, port=args.flock_port)


if __name__ == "__main__":
    asyncio.run(main())
