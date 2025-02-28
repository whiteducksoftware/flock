import uuid
from typing import Any

from pydantic import Field
from zep_python.client import Zep
from zep_python.types import Message as ZepMessage, SessionSearchResult

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.logging.logging import get_logger

logger = get_logger("module.zep")


class ZepModuleConfig(FlockModuleConfig):
    """Configuration for the Zep module."""

    zep_url: str = "http://localhost:8000"
    zep_api_key: str = "apikey"
    min_fact_rating: float = Field(
        default=0.7, description="Minimum rating for facts to be considered"
    )
    enable_read: bool = True
    enable_write: bool = False


class ZepModule(FlockModule):
    """Module that adds Zep capabilities to a Flock agent."""

    name: str = "zep"
    config: ZepModuleConfig = ZepModuleConfig()
    session_id: str | None = None
    user_id: str | None = None

    def __init__(self, name, config: ZepModuleConfig) -> None:
        """Initialize Zep module."""
        super().__init__(name=name, config=config)
        logger.debug("Initializing Zep module")
        zep_client = Zep(
            base_url=self.config.zep_url, api_key=self.config.zep_api_key
        )
        self.user_id = self.name
        self._setup_user(zep_client)
        self.session_id = str(uuid.uuid4())
        self._setup_session(zep_client)

    def _setup_user(self, zep_client: Zep) -> None:
        """Set up user in Zep."""
        if not zep_client or not self.user_id:
            raise ValueError("Zep service or user_id not initialized")

        try:
            user = zep_client.user.get(user_id=self.user_id)
            if not user:
                zep_client.user.add(user_id=self.user_id)
        except Exception:
            zep_client.user.add(user_id=self.user_id)

    def _setup_session(self, zep_client: Zep) -> None:
        """Set up new session."""
        if not zep_client or not self.user_id or not self.session_id:
            raise ValueError(
                "Zep service, user_id, or session_id not initialized"
            )

        zep_client.memory.add_session(
            user_id=self.user_id,
            session_id=self.session_id,
        )

    def get_client(self) -> Zep:
        """Get Zep client."""
        return Zep(
            base_url=self.config.zep_url, api_key=self.config.zep_api_key
        )

    def get_memory(self, zep_client: Zep) -> str | None:
        """Get memory for the current session."""
        if not zep_client or not self.session_id:
            logger.error("Zep service or session_id not initialized")
            return None

        try:
            memory = zep_client.memory.get(
                self.session_id, min_rating=self.config.min_fact_rating
            )
            if memory:
                return f"{memory.relevant_facts}"
        except Exception as e:
            logger.error(f"Error fetching memory: {e}")
            return None

        return None

    def split_text(
        self, text: str | None, max_length: int = 1000
    ) -> list[ZepMessage]:
        """Split text into smaller chunks."""
        result: list[ZepMessage] = []
        if not text:
            return result
        if len(text) <= max_length:
            return [ZepMessage(role="user", content=text, role_type="user")]
        for i in range(0, len(text), max_length):
            result.append(
                ZepMessage(
                    role="user",
                    content=text[i : i + max_length],
                    role_type="user",
                )
            )
        return result

    def add_to_memory(self, text: str, zep_client: Zep) -> None:
        """Add text to memory."""
        if not zep_client or not self.session_id:
            logger.error("Zep service or session_id not initialized")
            return

        messages = self.split_text(text)
        zep_client.memory.add(session_id=self.session_id, messages=messages)

    def search_memory(
        self, query: str, zep_client: Zep
    ) -> list[SessionSearchResult]:
        """Search memory for a query."""
        if not zep_client or not self.user_id:
            logger.error("Zep service or user_id not initialized")
            return []

        response = zep_client.memory.search_sessions(
            text=query,
            user_id=self.user_id,
            search_scope="facts",
            min_fact_rating=self.config.min_fact_rating,
        )
        if not response.results:
            return []
        return response.results

    async def post_evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Format and display the output."""
        if not self.config.enable_write:
            return result
        logger.debug("Saving data to memory")
        zep_client = Zep(
            base_url=self.config.zep_url, api_key=self.config.zep_api_key
        )
        self.add_to_memory(str(result), zep_client)
        return result

    async def pre_evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Format and display the output."""
        if not self.config.enable_read:
            return inputs

        zep_client = Zep(
            base_url=self.config.zep_url, api_key=self.config.zep_api_key
        )

        logger.debug("Searching memory")
        facts = self.search_memory(str(inputs), zep_client)

        # Add memory to inputs
        facts_str = ""
        if facts:
            for fact in facts:
                facts_str += fact.fact.fact + "\n"
            logger.debug("Found facts in memory: {}", facts_str)
            agent.input = agent.input + ", memory"
            inputs["memory"] = facts_str

        return inputs
