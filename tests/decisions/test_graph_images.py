"""Dashboard graph data for images: thumbnails, decider lanes, decision subjects."""

from __future__ import annotations

import io

import pytest
from PIL import Image as PILImage
from pydantic import BaseModel

from flock.api.collector import DashboardEventCollector
from flock.api.graph_builder import GraphAssembler
from flock.components.server.models.graph import GraphRequest
from flock.core import Flock
from flock.core.image import Image
from flock.decisions import Choice, Decision, FakeDecider
from flock.registry import flock_type, type_registry


def square(rgb: tuple[int, int, int], size: int = 600) -> Image:
    return Image.from_pil(PILImage.new("RGB", (size, size), rgb))


@flock_type
class GraphSwatch(BaseModel):
    name: str
    photo: Image


class GraphColor(Choice):
    """What is the color of the square in the image?"""

    red = "Red"
    blue = "Blue"


def by_name(state: str) -> dict[str, float]:
    if "red" in state:
        return {"red": 0.97, "blue": 0.03}
    if "blue" in state:
        return {"red": 0.04, "blue": 0.96}
    return {"red": 0.5, "blue": 0.5}


@pytest.fixture
async def sorted_swatches() -> Flock:
    flock = Flock()
    flock.is_dashboard = True
    flock.agent("painter").consumes(GraphSwatch).decides(
        GraphColor, model=FakeDecider(by_name), threshold=0.8
    )
    collector = DashboardEventCollector(store=flock.store)
    for agent in flock.agents:
        agent._add_utilities([collector])
    flock._test_collector = collector
    for name, rgb in [
        ("red one", (220, 30, 30)),
        ("blue one", (30, 60, 220)),
        ("red two", (200, 40, 40)),
        ("grey", (128, 128, 128)),
    ]:
        await flock.publish(GraphSwatch(name=name, photo=square(rgb)))
    await flock.run_until_idle()
    return flock


async def snapshot(flock: Flock, view_mode: str):
    assembler = GraphAssembler(flock.store, flock._test_collector, flock)
    return await assembler.build_snapshot(GraphRequest(view_mode=view_mode))


def decoded(data_url: str) -> PILImage.Image:
    return PILImage.open(io.BytesIO(Image(url=data_url).to_bytes()))


async def test_image_artifacts_carry_thumbnails_not_full_images(sorted_swatches):
    graph = await snapshot(sorted_swatches, "blackboard")
    swatch_type = type_registry.name_for(GraphSwatch)

    node = next(
        n
        for n in graph.nodes
        if n.data["artifactType"] == swatch_type
        and n.data["payload"]["name"] == "red one"
    )
    [image] = node.data["images"]
    assert image["path"] == "photo"
    assert image["mime"] == "image/jpeg"
    assert max(decoded(image["thumb"]).size) <= 160
    assert len(image["thumb"]) < len(square((220, 30, 30)).url)
    assert node.data["payload"]["photo"].startswith("🖼 image/jpeg")


async def test_decider_lanes_hold_thumbnails_per_option(sorted_swatches):
    graph = await snapshot(sorted_swatches, "agent")

    painter = next(n for n in graph.nodes if n.id == "painter")
    samples = painter.data["decision"]["questions"][0]["samples"]
    assert [round(s["p"], 2) for s in samples["red"]] == [0.97, 0.97]
    assert [round(s["p"], 2) for s in samples["blue"]] == [0.96]
    assert [round(s["p"], 2) for s in samples["UNSURE"]] == [0.5]
    assert all(s["thumb"].startswith("data:image/") for s in samples["red"])


async def test_decision_artifacts_show_their_subject_image(sorted_swatches):
    graph = await snapshot(sorted_swatches, "blackboard")
    decision_type = type_registry.name_for(Decision.of(GraphColor))

    decisions = [
        n.data["decision"]
        for n in graph.nodes
        if n.data["artifactType"] == decision_type
    ]
    assert len(decisions) == 4
    assert all(d["subjectThumb"].startswith("data:image/") for d in decisions)
