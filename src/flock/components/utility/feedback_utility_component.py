"""Feedback utility component for learning from user feedback."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from flock.core.component.agent_component_base import AgentComponentConfig
from flock.core.component.utility_component import UtilityComponent
from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.core.registry import flock_component

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent
    from flock.webapp.app.services.sharing_models import FeedbackRecord
    from flock.webapp.app.services.sharing_store import SharedLinkStoreInterface

logger = get_logger("components.utility.feedback")


class FeedbackUtilityConfig(AgentComponentConfig):
    """Configuration for the FeedbackUtilityComponent."""
    
    # Storage configuration
    storage_type: Literal["sqlite", "azure"] = Field(
        default="sqlite",
        description="Type of storage backend for feedback data"
    )
    
    # SQLite configuration
    sqlite_db_path: str = Field(
        default="./flock_feedback.db",
        description="Path to SQLite database file"
    )
    
    # Azure Table Storage configuration
    azure_connection_string: str | None = Field(
        default=None,
        description="Azure Table Storage connection string"
    )
    azure_table_name: str = Field(
        default="flockfeedback",
        description="Azure Table Storage table name"
    )
    
    # Feedback selection criteria
    max_feedback_items: int = Field(
        default=5,
        description="Maximum number of feedback items to include"
    )
    feedback_timeframe_days: int = Field(
        default=30,
        description="Only include feedback from the last N days"
    )
    
    # Feedback injection settings
    feedback_input_key: str = Field(
        default="feedback_context",
        description="Input key to use for injected feedback"
    )
    include_expected_responses: bool = Field(
        default=True,
        description="Whether to include expected responses from feedback"
    )
    include_actual_responses: bool = Field(
        default=False,
        description="Whether to include actual responses from feedback"
    )
    
    # Feedback filtering
    feedback_filter_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to filter feedback (only include feedback containing these)"
    )
    feedback_exclude_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to exclude feedback containing these"
    )


@flock_component(config_class=FeedbackUtilityConfig)
class FeedbackUtilityComponent(UtilityComponent):
    """Utility component that injects relevant feedback into agent inputs."""
    
    config: FeedbackUtilityConfig = Field(
        default_factory=FeedbackUtilityConfig,
        description="Feedback component configuration"
    )
    
    def __init__(self, name: str = "feedback", config: FeedbackUtilityConfig | None = None, **data):
        super().__init__(name=name, config=config or FeedbackUtilityConfig(), **data)
        self._store: SharedLinkStoreInterface | None = None
    
    async def _get_store(self) -> SharedLinkStoreInterface:
        """Get the appropriate feedback store based on configuration."""
        if self._store is None:
            if self.config.storage_type == "sqlite":
                from flock.webapp.app.services.sharing_store import SQLiteSharedLinkStore
                self._store = SQLiteSharedLinkStore(self.config.sqlite_db_path)
            elif self.config.storage_type == "azure":
                if not self.config.azure_connection_string:
                    raise ValueError("Azure connection string is required for Azure storage")
                from flock.webapp.app.services.sharing_store import AzureTableSharedLinkStore
                self._store = AzureTableSharedLinkStore(
                    connection_string=self.config.azure_connection_string,
                    table_name=self.config.azure_table_name
                )
            else:
                raise ValueError(f"Unsupported storage type: {self.config.storage_type}")
            
            await self._store.initialize()
        
        return self._store
