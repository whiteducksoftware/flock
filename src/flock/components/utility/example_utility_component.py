"""Example utility component for n-shot learning."""

from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import Field

from flock.core.component.agent_component_base import AgentComponentConfig
from flock.core.component.utility_component import UtilityComponent
from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.core.registry import flock_component

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent
    from flock.webapp.app.services.sharing_store import SharedLinkStoreInterface

logger = get_logger("components.utility.example")


class ExampleUtilityConfig(AgentComponentConfig):
    """Configuration for the ExampleUtilityComponent."""
    
    # Storage configuration
    storage_type: Literal["sqlite", "azure"] = Field(
        default="sqlite",
        description="Type of storage backend for example data"
    )
    
    # SQLite configuration
    sqlite_db_path: str = Field(
        default="./flock_examples.db",
        description="Path to SQLite database file"
    )
    
    # Azure Table Storage configuration
    azure_connection_string: str | None = Field(
        default=None,
        description="Azure Table Storage connection string"
    )
    azure_table_name: str = Field(
        default="flockexamples",
        description="Azure Table Storage table name"
    )
    
    # Example selection criteria
    max_examples: int = Field(
        default=5,
        description="Maximum number of examples to include"
    )
    example_timeframe_days: int = Field(
        default=30,
        description="Only include examples from the last N days"
    )
    
    # Example injection settings
    example_input_key: str = Field(
        default="examples_context",
        description="Input key to use for injected examples"
    )
    
    # Example filtering
    example_filter_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to filter examples (only include examples containing these)"
    )
    example_exclude_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to exclude examples containing these"
    )


@flock_component(config_class=ExampleUtilityConfig)
class ExampleUtilityComponent(UtilityComponent):
    """Utility component that injects relevant examples into agent inputs for n-shot learning."""
    
    config: ExampleUtilityConfig = Field(
        default_factory=ExampleUtilityConfig,
        description="Example component configuration"
    )
    
    def __init__(self, name: str = "examples", config: ExampleUtilityConfig | None = None, **data):
        super().__init__(name=name, config=config or ExampleUtilityConfig(), **data)
        self._store: SharedLinkStoreInterface | None = None
    
    async def _get_store(self) -> SharedLinkStoreInterface:
        """Get the appropriate example store based on configuration."""
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
    
    @staticmethod
    def seed_examples(examples: list["ExampleRecord"]) -> None:
        """Seed examples into the storage system.
        
        Args:
            examples: List of ExampleRecord objects to seed
        """
        import asyncio
        
        async def _seed_examples():
            # Create a default component for seeding
            component = ExampleUtilityComponent()
            store = await component._get_store()
            
            for example in examples:
                await store.save_example(example)
            
            logger.info(f"Seeded {len(examples)} examples into storage")
        
        # Run the async function
        asyncio.run(_seed_examples())
    
    async def _get_relevant_examples(
        self, 
        agent_name: str, 
        inputs: dict[str, Any]
    ) -> list["ExampleRecord"]:
        """Get relevant examples for the given agent and inputs."""
        store = await self._get_store()
        
        # Get all examples for this agent
        all_examples = await store.get_all_examples_for_agent(agent_name)
        
        # Filter by timeframe
        cutoff_date = datetime.utcnow() - timedelta(days=self.config.example_timeframe_days)
        filtered_examples = [
            ex for ex in all_examples 
            if ex.created_at >= cutoff_date
        ]
        
        # Filter by keywords if specified
        if self.config.example_filter_keywords:
            filtered_examples = [
                ex for ex in filtered_examples
                if any(keyword.lower() in ex.content.lower() for keyword in self.config.example_filter_keywords)
            ]
        
        # Exclude by keywords if specified
        if self.config.example_exclude_keywords:
            filtered_examples = [
                ex for ex in filtered_examples
                if not any(keyword.lower() in ex.content.lower() for keyword in self.config.example_exclude_keywords)
            ]
        
        # Sort by recency and limit
        filtered_examples.sort(key=lambda ex: ex.created_at, reverse=True)
        return filtered_examples[:self.config.max_examples]
    
    def _format_examples_for_injection(
        self, 
        example_records: list["ExampleRecord"]
    ) -> str:
        """Format example records for injection into agent input."""
        if not example_records:
            return "No relevant examples available."
        
        formatted_parts = []
        formatted_parts.append(f"Here are {len(example_records)} examples to guide your response:")
        
        for i, ex in enumerate(example_records, 1):
            ex_text = f"\nExample {i} (ID: {ex.example_id}):"
            ex_text += f"\n{ex.content}"
            ex_text += f"\nDate: {ex.created_at.strftime('%Y-%m-%d')}"
            formatted_parts.append(ex_text)
        
        return "\n".join(formatted_parts)
    
    async def on_pre_evaluate(
        self,
        agent: "FlockAgent",
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Inject relevant examples into agent inputs before evaluation."""
        logger.debug(f"Injecting examples for agent '{agent.name}'")
        
        try:
            # Get relevant examples for this agent
            example_records = await self._get_relevant_examples(agent.name, inputs)
            
            # Format examples for injection
            formatted_examples = self._format_examples_for_injection(example_records)
            
            # Create a copy of inputs to avoid modifying the original
            enhanced_inputs = inputs.copy()
            
            # Inject examples using the configured key
            enhanced_inputs[self.config.example_input_key] = formatted_examples
            
            logger.debug(f"Injected {len(example_records)} examples into '{self.config.example_input_key}'")
            
            return enhanced_inputs
            
        except Exception as e:
            logger.error(f"Error injecting examples: {e}")
            # Return original inputs if example injection fails
            return inputs


# Example record model
class ExampleRecord:
    """Record for storing example data."""
    
    def __init__(
        self,
        agent_name: str,
        example_id: str,
        content: str,
        created_at: datetime | None = None
    ):
        self.agent_name = agent_name
        self.example_id = example_id
        self.content = content
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "agent_name": self.agent_name,
            "example_id": self.example_id,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "context_type": "example"
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExampleRecord":
        """Create from dictionary from storage."""
        return cls(
            agent_name=data["agent_name"],
            example_id=data["example_id"],
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"])
        )
