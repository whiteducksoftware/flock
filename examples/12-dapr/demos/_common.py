"""Shared pieces for the Dapr demos: artifact types, secrets, and the store.

Both ``writer.py`` and ``reader.py`` import from here so that the two Flock
instances agree on the artifact types and on the Dapr state store they share.
"""

from __future__ import annotations

import os

from dapr.clients import DaprClient
from pydantic import BaseModel, Field

from flock import flock_type
from flock.storage import (
    DaprStateBlackboardConfig,
    DaprStateBlackboardStore,
    DaprStateBlackboardStoreClientConfig,
)


# ── Artifact types ───────────────────────────────────────────────────
# Same types as the redis_encrypted example, plus ``Review`` for demo 2.
# Explicit names keep REST payloads short (``"type": "BandConcept"``) and
# identical across both processes; the default would be ``_common.BandConcept``.


@flock_type(name="BandConcept")
class BandConcept(BaseModel):
    genre: str = Field(description="Musical genre (rock, jazz, metal, pop, etc.)")
    vibe: str = Field(description="The band's vibe or aesthetic")
    target_audience: str = Field(description="Who should love this band?")


@flock_type(name="BandLineup")
class BandLineup(BaseModel):
    band_name: str = Field(description="Cool band name")
    members: list[dict[str, str]] = Field(description="Band members with their roles")
    origin_story: str = Field(description="How the band formed", min_length=100)
    signature_sound: str = Field(description="What makes their sound unique")


@flock_type(name="Album")
class Album(BaseModel):
    title: str = Field(description="Album title in ALL CAPS")
    tracklist: list[dict[str, str]] = Field(
        description="Songs with titles and brief descriptions",
        min_length=8,
        max_length=12,
    )
    genre_fusion: str = Field(description="How this album blends genres")
    standout_track: str = Field(description="The track that'll be a hit")
    production_notes: str = Field(description="Special production techniques")


@flock_type(name="MarketingCopy")
class MarketingCopy(BaseModel):
    press_release: str = Field(
        description="Press release announcing the album", min_length=200
    )
    social_media_hook: str = Field(
        description="Catchy social post (280 chars max)", max_length=280
    )
    billboard_tagline: str = Field(
        description="10-word tagline for billboards", max_length=100
    )
    target_playlists: list[str] = Field(
        description="Spotify/Apple Music playlists to pitch to",
        min_length=3,
        max_length=5,
    )


@flock_type(name="Review")
class Review(BaseModel):
    verdict: str = Field(
        description="Ship it | Needs work | Burn it",
        pattern="^(Ship it|Needs work|Burn it)$",
    )
    score: int = Field(
        description="1 (unlistenable) to 10 (album of the year)", ge=1, le=10
    )
    reasoning: str = Field(
        description="Why, in the voice of a merciless critic", min_length=50
    )


# ── Secrets via the Dapr secret store ────────────────────────────────

SECRET_STORE = "flock-dev-secretstore"
SECRET_KEYS = (
    "api_key",
    "base_url",
    "api_version",
    "state_store_name",
    "default_model",
)


def load_secrets() -> dict[str, str]:
    """Read the LLM credentials and the store name from the Dapr secret store."""
    secrets: dict[str, str] = {}
    with DaprClient() as client:
        for key in SECRET_KEYS:
            value = client.get_secret(store_name=SECRET_STORE, key=key).secret.get(key)
            if not value:
                raise ValueError(
                    f"secret {key!r} missing in {SECRET_STORE} (check secrets.json)"
                )
            secrets[key] = value
    return secrets


def configure_model_env(secrets: dict[str, str]) -> None:
    """Export the provider variables LiteLLM expects for ``default_model``."""
    model = secrets["default_model"]
    if model.startswith("azure/"):
        os.environ["AZURE_API_KEY"] = secrets["api_key"]
        os.environ["AZURE_API_BASE"] = secrets["base_url"]
        os.environ["AZURE_API_VERSION"] = secrets["api_version"]
    else:
        os.environ["OPENAI_API_KEY"] = secrets["api_key"]
        if secrets["base_url"] != "-":
            os.environ["OPENAI_API_BASE"] = secrets["base_url"]


# ── The shared store ─────────────────────────────────────────────────


def make_store(store_name: str) -> DaprStateBlackboardStore:
    """Dapr-backed blackboard store for the encrypted Redis stack.

    Encryption and transactions cannot be combined (Dapr runtime limitation),
    so transactions are off explicitly. ETags give first-write-wins on the
    indexes when two instances write at the same time.
    """
    config = DaprStateBlackboardConfig(
        store_name=store_name,
        encrypted_backend=True,
        supports_transactions=False,
        supports_etag=True,
        etag_max_retries=5,
        consistency="strong",
        supports_dapr_query_lang=False,
        client_config=DaprStateBlackboardStoreClientConfig(),
    )
    return DaprStateBlackboardStore(config=config)
