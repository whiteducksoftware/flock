"""Run a decision example with fake decision models and scripted LLM answers.

For screenshots and videos: no API keys, no costs. Usage:

    python fake_models.py EXAMPLE.py [--port 8350] [--cli] [--fast]

--cli runs the example's command-line mode (to tune the answers), --fast
skips the models' thinking time.
"""

from __future__ import annotations

import argparse
import asyncio
import colorsys
import hashlib
import importlib.util
import math
import os
import re
import sys
from dataclasses import replace

os.environ.setdefault("BROWSER", "/bin/true")
os.environ.setdefault("FLOCK_AUTO_TRACE", "false")
# The examples' documented LLM, not a deployment from a local .env (it shows in the dashboard)
os.environ["DEFAULT_MODEL"] = "openai/gpt-4.1"

parser = argparse.ArgumentParser()
parser.add_argument("example")
parser.add_argument("--port", type=int, default=8350)
parser.add_argument("--cli", action="store_true")
parser.add_argument("--fast", action="store_true")
ARGS = parser.parse_args()

from flock.decisions import providers as P  # noqa: E402

WORD = re.compile(r"[a-z][a-z]{2,}")
STOP = set(
    """the and for with that this from are was were has have had not but its into
    our your their them they you any all can will would should could about than then
    also which what when where who whom how why each other more most such only own
    same some very just over under after before again further once here there both
    does did doing being been out off per via upon onto across along among around
    question answer option options shape shapes""".split()
)
SUFFIXES = ("ing", "ies", "es", "ed", "ly", "s")


def stem(word: str) -> str:
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            word = word[: -len(suffix)]
            break
    return word[:7]


def words(text: str) -> set[str]:
    return {stem(w) for w in WORD.findall(text.lower()) if w not in STOP}


def unit(*parts: str) -> float:
    """A stable number in [0, 1) for the parts."""
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def skill(label: str) -> float:
    """Bigger models are surer and right more often."""
    label = label.lower()
    if "luna" in label or "gpt" in label:
        return 0.87
    if "jev" in label:
        return 0.79
    if "local" in label or "clef" in label:
        return 0.6
    return 0.84  # decision-1


# --- What the examples' data says is right ----------------------------------

DATA = os.path.join(os.path.dirname(os.path.abspath(ARGS.example)), "data")


def _load(name):
    import json

    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        return json.load(handle)


PAPERS = _load("arxiv_abstracts.json")
DOCUMENTS = _load("compliance_documents.json")
EVIDENCE = [
    (item["text"], item.get("control") or item.get("control_id"))
    for doc in DOCUMENTS
    for item in (doc.get("evidence") if isinstance(doc.get("evidence"), list) else [])
    if isinstance(item, dict)
]


def labels_of(doc) -> dict:
    labels = doc.get("labels") or {}
    if isinstance(labels, str):
        import ast

        labels = ast.literal_eval(labels)
    return labels


def norm(text: str) -> str:
    """Letters and digits only: the state comes JSON-escaped (umlauts, backslashes)."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def truth_choice(state: str, options) -> str | None:
    flat = norm(state)
    for paper in PAPERS:
        if paper["field"] in options and (paper["arxiv_id"] in state or norm(paper["title"])[:50] in flat):
            return paper["field"]
    for text, control in EVIDENCE:
        if control in options and norm(text)[:60] in flat:
            return control
    return None


def truth_item(state: str, item: str | None) -> str | None:
    if not item:
        return None
    flat = norm(state)
    for doc in DOCUMENTS:
        if norm(doc["text"])[:80] in flat or doc["id"] in state:
            return labels_of(doc).get(item)
    # A section of a document (any of its sentences is here): what its evidence
    # sentences show in this section, else no
    for doc in DOCUMENTS:
        sentences = [norm(part)[:50] for part in re.split(r"(?<=[.!?])\s+", doc["text"]) if len(norm(part)) >= 30]
        if any(sentence in flat for sentence in sentences):
            shown = [e for e in doc.get("evidence", []) if isinstance(e, dict) and norm(e["text"])[:60] in flat]
            return "yes" if any(e.get("control") == item for e in shown) else "no"
    return None


# Words that point to an option where the data knows no answer (tickets' tone and urgency)
SIGNALS = {
    "furious": ["cancel", "tell everyone", "again", "third time"],
    "angry": ["unacceptable", "fix it now", "wiped", "i paid"],
    "annoyed": ["fails", "error", "crashed", "don't recognise", "weird"],
    "calm": ["hi!", "lovely", "thanks", "could you", "no rush", "some day"],
    "yes": ["today", " now", "two hours", "before my", "outage", "asap"],
    "no": ["no rush", "some day", "whenever", "could you"],
}


def signalled(state: str, options) -> str | None:
    """The option the most signal words point to (the later one on a tie: the stronger level)."""
    text = state.lower()
    counts = {o: sum(text.count(word) for word in SIGNALS.get(o.lower(), ())) for o in options}
    best = max(counts.values(), default=0)
    if best == 0:
        return None
    return [o for o in options if counts[o] == best][-1]


# --- Images: the hue of the shape --------------------------------------------

# Hues of the color sorter's palette
COLORS = {"red": 0.0, "orange": 0.085, "yellow": 0.142, "green": 0.372, "blue": 0.630, "purple": 0.769}


def image_hue(images) -> float | None:
    """The hue of an image's most saturated pixels (the shape, not the paper)."""
    try:
        import io

        from PIL import Image as PILImage

        pil = PILImage.open(io.BytesIO(images[0].to_bytes())).convert("RGB").resize((48, 48))
    except Exception:
        return None
    hues = [
        h
        for h, s, v in (colorsys.rgb_to_hsv(r / 255, g / 255, b / 255) for r, g, b in pil.get_flattened_data())
        if s > 0.35 and v > 0.25
    ]
    if not hues:
        return None
    x = sum(math.cos(2 * math.pi * h) for h in hues)
    y = sum(math.sin(2 * math.pi * h) for h in hues)
    return (math.atan2(y, x) / (2 * math.pi)) % 1.0


def softmax(scores: dict[str, float]) -> dict[str, float]:
    top = max(scores.values())
    exp = {k: math.exp(v - top) for k, v in scores.items()}
    total = sum(exp.values())
    return {k: v / total for k, v in exp.items()}


class ShotDecider(P.DecisionProvider):
    """A model with a skill: right more often on easy inputs, surer when right.

    Where the example's data knows the answer it answers around it; else it
    goes by the words the state shares with each option's criteria. Hard
    inputs are hard for every model, and models confuse the same rival.
    """

    supports_images = True

    def __init__(self, label: str):
        self.label = label
        self.skill = skill(label)

    def _fit(self, state: str, option: str, criteria: str, images) -> float:
        hue = image_hue(images) if images else None
        if hue is not None and option.lower() in COLORS:
            target = COLORS[option.lower()]
            distance = min(abs(hue - target), 1 - abs(hue - target))
            return max(0.0, 1 - distance * 6)
        wanted = words(f"{option.replace('_', ' ')} {criteria}")
        return len(words(state) & wanted) / math.sqrt(len(wanted) + 1)

    def _around(self, state: str, key: str, truth: str, options: list[str], ease: float = 1.0) -> dict[str, float]:
        """Probabilities around the right answer, for this model's skill."""
        # Hard for every model, and a little in each model's own way (clear cues make it easier)
        hard = ease * (0.65 * unit("difficulty", state[:300], key) + 0.35 * unit(self.label, "own", state[:300], key))
        noise = unit(self.label, state[:300], key)
        rivals = [o for o in options if o != truth]
        rival = rivals[int(unit("rival", state[:300], key) * len(rivals))] if rivals else truth
        wrong = noise < hard * (1 - self.skill) * 0.55
        top, second = (rival, truth) if wrong else (truth, rival)
        # Sure while the input is easier than the model is good, and then very sure,
        # as decision models are: at 0.8 firm on about 87 % (decision-1), 89 % (jev)
        # and 95 % (gpt-6-luna) of the arXiv abstracts, as measured in the guide
        logit = 19 * (self.skill - hard) + 0.8 + (unit(self.label, "sure", state[:300], key) - 0.5)
        sure = 0.33 + 0.665 / (1 + math.exp(-logit))
        rest = 1 - sure
        probabilities = {o: 0.0 for o in options}
        probabilities[top] = sure
        if len(options) == 1:
            return probabilities
        others = [o for o in options if o not in (top, second)]
        share = 0.6 + 0.3 * unit(self.label, "share", state[:200], key)
        probabilities[second] = rest * (share if others else 1.0)
        for index, option in enumerate(others):
            weight = unit(self.label, option, state[:200])
            probabilities[option] = rest * (1 - share) * weight
        total = sum(probabilities.values())
        return {o: p / total for o, p in probabilities.items()}

    def _choice(self, state: str, question, images) -> dict[str, float]:
        options = list(question.options)
        if images and all(o.lower() in COLORS for o in options):
            # Pure colors near 1.00, in-between colors 0.85-0.95 for the nearer bin
            return softmax({o: 13 * self._fit(state, o, "", images) for o in options})
        truth = truth_choice(state, options)
        cue = None if truth else signalled(state, options)
        if cue is not None:
            return self._around(state, question.label, cue, options, ease=1.5 if question.kind == "scale" else 0.4)
        if truth is None:
            fits = {o: self._fit(state, o, c, images) for o, c in question.options.items()}
            best = max(fits.values())
            if best > 0 and list(fits.values()).count(best) == 1:
                truth = max(fits, key=fits.__getitem__)
        if truth is not None:
            return self._around(state, question.label, truth, options)
        # Nothing to go by: a spread a model would not be sure about
        return softmax({o: 2.5 * unit(self.label, state[:300], question.label, o) for o in options})

    def _yes(self, state: str, question) -> float:
        truth = truth_item(state, question.item)
        if truth in ("yes", "no"):
            return self._around(state, question.label, truth, ["yes", "no"])["yes"]
        if question.item:
            # A checklist item the text gives nothing for (a heading, a short line): no
            return self._around(state, question.label, "no", ["yes", "no"], ease=0.5)["yes"]
        cue = None if question.item else signalled(state, ["no", "yes"])
        if cue is not None:
            return self._around(state, question.label, cue, ["yes", "no"], ease=0.4)["yes"]
        wanted = words(f"{question.item or ''} {question.options.get('yes', '')}")
        fit = len(words(state) & wanted) / math.sqrt(len(wanted) + 1)
        jitter = unit(self.label, state[:300], question.label) - 0.5
        logit = 4.0 * self.skill * (2.2 * fit - 0.5 + 1.1 * jitter)
        return 1 / (1 + math.exp(-logit))

    def _answer(self, state: str, question, images) -> P.DecisionAnswer:
        if set(question.options) == {"yes", "no"}:
            return P._yes_no_answer(self._yes(state, question))
        probabilities = self._choice(state, question, images)
        choice = max(probabilities, key=probabilities.__getitem__)
        score = (
            P._weighted_score(question, probabilities) if question.kind == "scale" else None
        )
        return P.DecisionAnswer(
            choice=choice,
            probabilities=probabilities,
            confidence=probabilities[choice],
            score=score,
        )

    async def decide_many(self, state, questions, images=()):
        if os.environ.get("SHOT_DEBUG"):
            import json as _json

            with open(os.environ["SHOT_DEBUG"], "a") as handle:
                handle.write(_json.dumps({"label": self.label, "state": state[:600], "truth": truth_choice(state, list(questions[0].options))}) + "\n")
        if not ARGS.fast:
            await asyncio.sleep(0.5 + unit(self.label, state[:200]) * 0.9)
        tokens = len(state) // 4
        return {
            q.name: P._check_options(
                self.label,
                q,
                replace(self._answer(state, q, images), model=self.label, input_tokens=tokens),
            )
            for q in questions
        }


_resolve = P.resolve_provider


def resolve(model):
    if isinstance(model, P.DecisionProvider):
        return model
    return ShotDecider(str(model))


P.resolve_provider = resolve


# --- LLMs: scripted answers -------------------------------------------------

from flock.engines.dspy_engine import DSPyEngine  # noqa: E402
from flock.utils.runtime import EvalResult  # noqa: E402

REPLIES = {
    "billing": "Thanks for flagging the double charge. I have refunded the second payment; you will see it on your card within three to five days.",
    "shipping": "Sorry your parcel is late. It left our warehouse on Monday and the carrier now expects it on Thursday; here is the tracking link.",
    "tech": "Sorry about the crash. Please update the app to the latest version; if it still closes at login, send us the time and we will check the logs.",
    "supervisor": "Thanks for your patience. I have looked at your case myself and will come back to you today with an answer.",
}


def _explain(inputs) -> dict:
    cases = next(
        (a.payload for a in inputs.artifacts if "decisions" in (a.payload or {})), None
    )
    subject = next((a.payload for a in inputs.artifacts if "decisions" not in (a.payload or {})), {})
    quote = str(subject.get("message") or subject.get("text") or next((v for v in subject.values() if isinstance(v, str)), ""))[:140]
    if not cases:
        return {"explanation": "Nothing to explain."}
    case = cases["decisions"][0]
    ranked = sorted(case.get("probabilities", {}).items(), key=lambda kv: -kv[1])
    (first, p1), (second, p2) = (ranked + [("", 0.0), ("", 0.0)])[:2]
    return {
        "explanation": (
            f"The ticket leans to {first} ({p1:.2f}): \u201c{quote.strip().rstrip('.')}\u201d. "
            f"{second.capitalize()} ({p2:.2f}) is not ruled out, because the ticket "
            f"does not say whether the customer needs {first} or {second}."
        ),
        "missing": f"Whether the customer needs help with {first} or with {second}.",
    }


def describe_picture(payload: dict) -> str | None:
    """'a red circle': the color of the shape by its hue, its kind by how much of its box it fills."""
    picture = next((v for v in payload.values() if isinstance(v, dict) and str(v.get("url", "")).startswith("data:image")), None)
    if picture is None:
        return None
    import io

    from PIL import Image as PILImage

    from flock import Image

    pil = PILImage.open(io.BytesIO(Image(**picture).to_bytes())).convert("RGB").resize((64, 64))
    points = [
        (i % 64, i // 64, colorsys.rgb_to_hsv(r / 255, g / 255, b / 255))
        for i, (r, g, b) in enumerate(pil.get_flattened_data())
    ]
    shape = [(x, y, h) for x, y, (h, s, v) in points if s > 0.35 and v > 0.25]
    if not shape:
        return None
    xs = [x for x, _, _ in shape]
    ys = [y for _, y, _ in shape]
    fill = len(shape) / ((max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1))
    kind = "square" if fill > 0.92 else "circle" if fill > 0.65 else "triangle"
    hue = (math.atan2(sum(math.sin(2 * math.pi * h) for *_, h in shape), sum(math.cos(2 * math.pi * h) for *_, h in shape)) / (2 * math.pi)) % 1.0
    names = {"red": 0.0, "orange": 0.08, "yellow": 0.16, "green": 0.33, "blue": 0.62, "purple": 0.78}
    color = min(names, key=lambda n: min(abs(hue - names[n]), 1 - abs(hue - names[n])))
    return f"{'an' if color[0] in 'aeiou' else 'a'} {color} {kind}"


def _value(name: str, annotation, inputs) -> object:
    for artifact in inputs.artifacts:
        payload = artifact.payload or {}
        if name in payload:
            return payload[name]
    text = str(annotation)
    if "int" in text:
        return 1
    if "float" in text:
        return 0.5
    if "bool" in text:
        return True
    if "list" in text:
        return []
    return f"{name.replace('_', ' ').capitalize()} for the request."


async def scripted_evaluate(self, agent, ctx, inputs, output_group):
    if not ARGS.fast:
        await asyncio.sleep(1.2)
    objects = []
    for output in output_group.outputs:
        model = output.spec.model
        fields = {}
        if model.__name__ == "Explanation":
            fields = _explain(inputs)
        if {"seen", "caption_is_correct"} <= set(model.model_fields):
            payload = inputs.artifacts[0].payload or {}
            seen = describe_picture(payload) or "a picture"
            fields = {"seen": seen, "caption_is_correct": seen == payload.get("caption")}
        for name, field in model.model_fields.items():
            if name in fields or not field.is_required():
                continue
            if name in {"reply", "text", "answer", "message"}:
                fields[name] = REPLIES.get(agent.name.split("_")[0], REPLIES["supervisor"])
            else:
                fields[name] = _value(name, field.annotation, inputs)
        objects.append(model(**fields))
    return EvalResult.from_objects(*objects, agent=agent)


DSPyEngine.evaluate = scripted_evaluate


# --- Item thresholds for a checklist decider (the calibration example has no dashboard)

if os.environ.get("SHOT_ITEM_THRESHOLDS"):
    import json as _json

    from flock.core.agent import AgentBuilder

    _decides = AgentBuilder.decides
    _items = _json.loads(os.environ["SHOT_ITEM_THRESHOLDS"])

    def decides(self, *questions, **kwargs):
        kwargs.setdefault("item_thresholds", _items)
        return _decides(self, *questions, **kwargs)

    AgentBuilder.decides = decides


# --- The example --------------------------------------------------------------

from flock import Flock  # noqa: E402

_serve = Flock.serve


async def serve(self, *args, **kwargs):
    kwargs["port"] = ARGS.port
    return await _serve(self, *args, **kwargs)


Flock.serve = serve

spec = importlib.util.spec_from_file_location("shot_example", ARGS.example)
example = importlib.util.module_from_spec(spec)
sys.modules["shot_example"] = example
spec.loader.exec_module(example)
if hasattr(example, "USE_DASHBOARD"):
    example.USE_DASHBOARD = not ARGS.cli
asyncio.run(example.main())
