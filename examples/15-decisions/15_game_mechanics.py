"""
Decision Models: Taking Game Ideas Apart, Three Models Compared

Sixty puzzle game ideas, each a title and a short pitch. A decision model
reads every idea once and answers six closed questions about it in one
request: five about the mechanic (what the player does, what the puzzle is
played on, whether information is hidden, how time works, what solves a
level) and one about the theme. Free text becomes structured data.

- one decision agent per entry in DECISION_MODELS, each
  `.decides(Action, Board, Hidden, Time, Goal, Theme)` on every idea
- all agents answer the same questions, so the report can compare them
  question by question

The report lists per model the median request time and how often it was
unsure, per question how often each pair of models and all three gave the
same firm answer, and the groups of ideas that share every mechanic answer:
the same game, and where the themes differ, the same game in a new costume.
Here an idea's answer is the option at least two models found most probable,
firm or not.

Before the run every decision model gets one warm-up request. Models whose
keys are missing or whose server does not answer are skipped.

🎯 Key Concepts:
- Several questions in one `.decides()`: one request per idea, one
  `Decision` per question
- `Choice` for one of several options, `YesNo` for a yes/no question
- The same questions on several deciders, one per model
- Decisions as data: the report reads them back from the store

🎛️  CONFIGURATION:
- DECISION_MODELS: which decision models answer
  - azure/decision-1: AZURE_API_BASE, AZURE_API_KEY
  - jev/jev-latest: JEV_API_KEY
  - openai/gpt-6-luna: OPENAI_API_KEY
- GAME_IDEAS: a JSON list of {"id", "title", "pitch"} (default:
  data/game_ideas.json)
- FACETS_OUT: if set, every answer is written to this JSON file
- USE_DASHBOARD = True serves the dashboard and publishes one idea every
  two seconds.

Data: data/game_ideas.json, 60 puzzle game ideas that two LLMs proposed in
an ideation experiment, some of them more than once.
"""

import asyncio
import itertools
import json
import os
import statistics
from collections import Counter
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from flock import Choice, Decision, Flock, YesNo
from flock.decisions.providers import DecisionQuestion, resolve_provider
from flock.registry import flock_type, type_registry


# ============================================================================
# 🎛️  CONFIGURATION
# ============================================================================
USE_DASHBOARD = False
DECISION_MODELS = ["azure/decision-1", "jev/jev-latest", "openai/gpt-6-luna"]
THRESHOLD = 0.6
CONCURRENCY = 4
IDEAS = Path(
    os.getenv("GAME_IDEAS", Path(__file__).parent / "data" / "game_ideas.json")
)
FACETS_OUT = os.getenv("FACETS_OUT")
# ============================================================================

console = Console()


@flock_type
class GameIdea(BaseModel):
    """A puzzle game idea: its name and what the player does."""

    idea_id: str
    title: str
    pitch: str


class Action(Choice):
    """What does the player mainly do to solve a level?"""

    place = "Place pieces, tiles, tools or markers on a board"
    move = "Move, push or steer pieces or a character through a space"
    connect = "Draw or build connections, paths, wires or routes"
    order = "Arrange things into an order or sequence, or schedule them"
    deduce = "Reveal or work out hidden information from clues or measurements"
    program = "Write a script, rules or instructions that then run on their own"
    transform = (
        "Rotate, fold, flip, rewrite or otherwise change the board or its pieces"
    )
    match = "Sort, match or combine items by their properties"


class Board(Choice):
    """What is the puzzle played on?"""

    grid = "A grid of cells or tiles"
    network = "A network of nodes and links"
    space = "Open space or a physics simulation"
    text = "Words, letters or sentences"
    objects = "Cards, a deck or a set of objects without a board"
    timeline = "A timeline, schedule or sequence of events"


class Hidden(YesNo):
    """Does the player have to work out information the game hides from them?"""


class Time(Choice):
    """How does time work in the puzzle?"""

    turns = "Nothing happens until the player acts, one move at a time"
    simulation = "The player sets things up, then a simulation runs"
    rewind = "The player rewinds, loops or replays time, or works with copies of earlier moves"
    realtime = "Things move in real time while the player acts"


class Goal(Choice):
    """What solves a level?"""

    reach = "Getting a piece or character to a target place"
    pattern = "Making the board match a target picture, pattern or state"
    constraints = "Satisfying every rule or constraint at once"
    deliver = "Delivering or routing items to their destinations"
    identify = "Naming the hidden answer: who, what or where"
    output = "Making a machine or simulation produce a required result"


class Theme(Choice):
    """What is the game's theme or setting, apart from its rules?"""

    nature = "Nature: animals, plants, weather, landscapes, caves"
    everyday = "Everyday life: home, kitchen, shops, streets, travel"
    work = "Work: offices, paperwork, factories, deliveries, trades"
    science = "Science and technology: labs, machines, light, sound, electricity"
    fantasy = "Fantasy and myth: magic, spirits, ghosts, fairy tales"
    history = "History: old crafts, historical places and events"
    stories = "Words and stories: letters, messages, books, gossip, theatre"
    future = "Space and science fiction: planets, robots, the future"
    abstract = "Abstract: shapes, colors and symbols without a story"


MECHANIC = (Action, Board, Hidden, Time, Goal)
QUESTIONS = (*MECHANIC, Theme)


def agent_name(model: str) -> str:
    return "facets_" + model.replace("/", "_").replace("-", "_").replace(".", "_")


async def ready_models() -> list[str]:
    """Warm up every decision model once; keep the ones that answer."""
    question = DecisionQuestion(
        name=Action.__name__,
        instructions=Action.__question__,
        options=Action.__options__,
    )
    ready = []
    for model in DECISION_MODELS:
        try:
            await resolve_provider(model).decide(
                'GameIdea: {"title": "Slide", "pitch": "Tilt the board until every block rests on a target."}',
                question,
            )
            ready.append(model)
        except Exception as exc:
            console.print(f"[dim]skipping {model}: {exc}[/dim]")
    return ready


def build_flock(models: list[str]) -> Flock:
    flock = Flock(decision_rate_limit="100/min", no_output=True)
    for model in models:
        (
            flock.agent(agent_name(model))
            .consumes(GameIdea)
            .decides(*QUESTIONS, model=model, threshold=THRESHOLD)
            .max_concurrency(CONCURRENCY)
        )
    return flock


def load_ideas() -> list[GameIdea]:
    return [
        GameIdea(idea_id=d["id"], title=d["title"], pitch=d["pitch"])
        for d in json.loads(IDEAS.read_text(encoding="utf-8"))
    ]


async def answers(flock: Flock) -> dict[str, dict[str, dict[str, dict]]]:
    """agent -> idea id -> question -> decision payload."""
    types = {type_registry.name_for(Decision.of(q)): q.__name__ for q in QUESTIONS}
    out: dict[str, dict[str, dict[str, dict]]] = {}
    for artifact in await flock.store.list():
        if artifact.type in types:
            out.setdefault(artifact.produced_by, {}).setdefault(
                artifact.correlation_id, {}
            )[types[artifact.type]] = artifact.payload
    return out


def firm(payload: dict | None) -> str | None:
    if payload is None or payload["choice"] == "UNSURE":
        return None
    return payload["choice"]


def majority(results, agents, idea_id: str, question: str) -> str | None:
    """The answer most models found most probable (firm or not), if at least two agree."""
    votes = Counter(
        p["best_guess"]
        for agent in agents
        if (p := results[agent].get(idea_id, {}).get(question)) and p.get("best_guess")
    )
    if not votes:
        return None
    answer, count = votes.most_common(1)[0]
    return answer if count >= min(2, len(agents)) else None


def report(results, models: list[str], ideas: list[GameIdea]) -> None:
    agents = [agent_name(m) for m in models if agent_name(m) in results]
    label = {agent_name(m): m for m in models}

    per_model = Table(
        title=f"{len(ideas)} ideas, {len(QUESTIONS)} questions per request"
    )
    per_model.add_column("Model")
    per_model.add_column("Ideas", justify="right")
    per_model.add_column("Request p50 ms", justify="right")
    per_model.add_column("Unsure", justify="right")
    for agent in agents:
        decisions = [p for idea in results[agent].values() for p in idea.values()]
        latencies = [p["latency_ms"] for p in decisions if p.get("latency_ms")]
        unsure = sum(firm(p) is None for p in decisions)
        per_model.add_row(
            label[agent],
            f"{len(results[agent])}",
            f"{statistics.median(latencies):.0f}" if latencies else "—",
            f"{unsure / max(1, len(decisions)):.0%}",
        )
    console.print(per_model)

    pairs = list(itertools.combinations(agents, 2))
    agreement = Table(title="Same firm answer (ideas where both or all were firm)")
    agreement.add_column("Question")
    for a, b in pairs:
        agreement.add_column(
            f"{label[a].split('/')[-1]} · {label[b].split('/')[-1]}", justify="right"
        )
    if len(agents) > 2:
        agreement.add_column("all", justify="right")
    for question in QUESTIONS:
        name = question.__name__
        row = []
        groups = pairs + ([tuple(agents)] if len(agents) > 2 else [])
        for group in groups:
            both = [
                [firm(results[a].get(i.idea_id, {}).get(name)) for a in group]
                for i in ideas
            ]
            both = [g for g in both if all(g)]
            same = sum(len(set(g)) == 1 for g in both)
            row.append(f"{same}/{len(both)}")
        agreement.add_row(name, *row)
    console.print(agreement)

    games: dict[tuple, list[tuple[GameIdea, str]]] = {}
    for idea in ideas:
        mechanic = tuple(
            majority(results, agents, idea.idea_id, q.__name__) for q in MECHANIC
        )
        theme = majority(results, agents, idea.idea_id, Theme.__name__)
        if all(mechanic) and theme:
            games.setdefault(mechanic, []).append((idea, theme))
    same = Table(
        title="Same game: ideas with the same answer to every mechanic question"
    )
    same.add_column("Mechanic (action, board, hidden, time, goal)")
    same.add_column("Ideas and their themes")
    same.add_column("New costume", justify="center")
    for mechanic, members in sorted(games.items(), key=lambda kv: -len(kv[1])):
        if len(members) > 1:
            same.add_row(
                " · ".join(mechanic),
                "\n".join(f"{idea.title} ({theme})" for idea, theme in members),
                "✓" if len({theme for _, theme in members}) > 1 else "",
            )
    console.print(same)
    console.print(
        f"{len(games)} distinct mechanics among {sum(map(len, games.values()))} ideas "
        f"on which at least two models agreed on every question"
    )


def write_facets(results, models: list[str], ideas: list[GameIdea]) -> None:
    out = [
        {
            "id": idea.idea_id,
            "title": idea.title,
            "answers": {
                model: {
                    q: {
                        k: p[k]
                        for k in ("choice", "best_guess", "probabilities", "latency_ms")
                    }
                    for q, p in results.get(agent_name(model), {})
                    .get(idea.idea_id, {})
                    .items()
                }
                for model in models
            },
        }
        for idea in ideas
    ]
    Path(FACETS_OUT).write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    console.print(f"Answers written to {FACETS_OUT}")


async def main_cli() -> None:
    ideas = load_ideas()
    models = await ready_models()
    flock = build_flock(models)
    console.print(
        f"\n🧩 {len(ideas)} game ideas, {len(QUESTIONS)} questions, "
        f"models: {', '.join(models)} (threshold {THRESHOLD})\n"
    )
    for idea in ideas:
        await flock.publish(idea, correlation_id=idea.idea_id)
    await flock.run_until_idle()
    results = await answers(flock)
    report(results, models, ideas)
    if FACETS_OUT:
        write_facets(results, models, ideas)


async def main_dashboard() -> None:
    flock = build_flock(await ready_models())

    async def feed():
        await asyncio.sleep(5)
        for idea in load_ideas():
            await flock.publish(idea, correlation_id=idea.idea_id)
            await asyncio.sleep(2)

    feeder = asyncio.create_task(feed())
    try:
        await flock.serve(dashboard=True)
    finally:
        feeder.cancel()


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
