import asyncio
import os

from dapr.clients import DaprClient
from pydantic import BaseModel, Field

from flock import Flock, PublicVisibility, flock_type
from flock.logging.logging import configure_logging, get_logger
from flock.storage.dapr import (
    DaprStateBlackboardConfig,
    DaprStateBlackboardStore,
    DaprStateBlackboardStoreClientConfig,
)


logger = get_logger(__name__)


@flock_type
class BandConcept(BaseModel):
    genre: str = Field(description="Musical genre (rock, jazz, metal, pop, etc.)")
    vibe: str = Field(description="The band's vibe or aesthetic")
    target_audience: str = Field(description="Who should love this band?")


@flock_type
class BandLineup(BaseModel):
    band_name: str = Field(description="Cool band name")
    members: list[dict[str, str]] = Field(
        description="List of band members with their roles"
    )
    origin_story: str = Field(description="How the band formed", min_length=100)
    signature_sound: str = Field(description="What makes their sound unique")


@flock_type
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


@flock_type
class MarketingCopy(BaseModel):
    press_release: str = Field(
        description="Professional press release announcing the album", min_length=200
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


FLOCK_SECRET_STORE = "flock-dev-secretstore"
FLOCK_BASE_URL_SECRET_KEY = "base_url"
FLOCK_API_VERSION_SECRET_KEY = "api_version"
FLOCK_API_KEY_SECRET_KEY = "api_key"
FLOCK_STATE_STORE_SECRET_KEY = "state_store_name"
FLOCK_DEFAULT_MODEL_SECRET_KEY = "default_model"


async def full_blown_flock_test():
    """Test the blackboard with a small team of agents."""
    # Configure global log levels
    configure_logging("ERROR", external_level="ERROR")
    # Get Dapr secrets
    base_url: str | None = None
    api_version: str | None = None
    state_store_name: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    with DaprClient() as client:
        logger.info(f"Retrieving {FLOCK_BASE_URL_SECRET_KEY} secret")
        base_url = client.get_secret(
            store_name=FLOCK_SECRET_STORE, key=FLOCK_BASE_URL_SECRET_KEY
        ).secret.get(FLOCK_BASE_URL_SECRET_KEY)
        logger.info(f"Got {FLOCK_BASE_URL_SECRET_KEY}")
        logger.info(f"Retrieving {FLOCK_API_VERSION_SECRET_KEY}")
        api_version = client.get_secret(
            store_name=FLOCK_SECRET_STORE, key=FLOCK_API_VERSION_SECRET_KEY
        ).secret.get(FLOCK_API_VERSION_SECRET_KEY)
        logger.info(f"Got {FLOCK_API_VERSION_SECRET_KEY}")
        logger.info(f"Retrieving {FLOCK_API_KEY_SECRET_KEY}")
        api_key = client.get_secret(
            store_name=FLOCK_SECRET_STORE, key=FLOCK_API_KEY_SECRET_KEY
        ).secret.get(FLOCK_API_KEY_SECRET_KEY)
        logger.info(f"Got {FLOCK_API_KEY_SECRET_KEY}")
        logger.info(f"Retrieving {FLOCK_STATE_STORE_SECRET_KEY}")
        state_store_name = client.get_secret(
            store_name=FLOCK_SECRET_STORE, key=FLOCK_STATE_STORE_SECRET_KEY
        ).secret.get(FLOCK_STATE_STORE_SECRET_KEY)
        logger.info(f"Retrieving {FLOCK_DEFAULT_MODEL_SECRET_KEY}")
        default_model = client.get_secret(
            store_name=FLOCK_SECRET_STORE, key=FLOCK_DEFAULT_MODEL_SECRET_KEY
        ).secret.get(FLOCK_DEFAULT_MODEL_SECRET_KEY)
        logger.info(f"Got {FLOCK_DEFAULT_MODEL_SECRET_KEY}")
    # Check if all keys have been retrieved
    # if one is missing, exit here and throw an exception
    if any([
        base_url is None,
        api_version is None,
        state_store_name is None,
        api_key is None,
        default_model is None,
    ]):
        logger.error("UNABLE TO RETRIEVE FULL LIST OF SECRETS!!!")
        raise ValueError
    # Set required environment-variables before creating Flock-instance
    os.environ["AZURE_API_BASE"] = base_url
    os.environ["AZURE_API_VERSION"] = api_version
    os.environ["AZURE_API_KEY"] = api_key
    # Initialize dapr store.
    # In-memory: no encryption, no transactions, no TTL, no query API.
    client_config = DaprStateBlackboardStoreClientConfig()
    store_config = DaprStateBlackboardConfig(
        store_name=state_store_name,
        supports_ttl=False,
        encrypted_backend=False,
        backend_encryption_key=None,
        supports_transactions=False,
        entries_ttl_seconds=None,
        client_config=client_config,
        supports_dapr_query_lang=False,
        supports_etag=False,
        consistency="eventual",
    )
    dapr_store = DaprStateBlackboardStore(config=store_config)
    # Initialize Flock Agent Swarm
    flock = Flock(
        model=default_model,
        max_agent_iterations=100,
        no_output=True,
        store=dapr_store,  # Add Dapr Blackboard Store as backend
    )
    _ = (
        flock.agent("talent_scout")
        .description("A legendary talent scout who assembles perfect band lineups")
        .consumes(BandConcept)
        .publishes(BandLineup, visibility=PublicVisibility())
    )
    _ = (
        flock.agent("music_producer")
        .description("A visionary music producer who creates debut album concepts")
        .consumes(BandLineup)
        .publishes(Album, visibility=PublicVisibility())
    )
    _ = (
        flock.agent("marketing_guru")
        .description("A marketing genius who writes compelling promotional material")
        .consumes(Album)
        .publishes(MarketingCopy, visibility=PublicVisibility())
    )

    await flock.serve(dashboard=True)


async def main_test():
    print("Liftoff!")
    print("=== Testing Flock with an In-Memory Backend ===")
    await full_blown_flock_test()


if __name__ == "__main__":
    asyncio.run(main_test())
