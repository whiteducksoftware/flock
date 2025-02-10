"""A context object for storing state, history, and agent definitions."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

from flock.core.context.context_vars import FLOCK_LAST_AGENT, FLOCK_LAST_RESULT
from flock.core.util.serializable import Serializable


@dataclass
class AgentRunRecord:
    """A record of an agent run, including the agent name, data, and timestamp."""

    agent: str = field(default="")  # Agent name
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default="")
    hand_off: dict = field(default=dict)  # Next agent name
    called_from: str = field(default="")  # Previous agent name


@dataclass
class AgentDefinition:
    """A serializable definition for an agent, including the agent type, name, and data."""

    agent_type: str = field(default="")
    agent_name: str = field(default="")
    agent_data: dict = field(default=dict)
    serializer: Literal["json", "cloudpickle", "msgpack"] = field(
        default="cloudpickle"
    )


@dataclass
class FlockContext(Serializable):
    """A context object for storing state, history, and agent definitions."""

    state: dict[str, Any] = field(default_factory=dict)
    history: list[AgentRunRecord] = field(default_factory=list)
    agent_definitions: dict[str, AgentDefinition] = field(default_factory=dict)
    run_id: str = field(default="")
    workflow_id: str = field(default="")
    workflow_timestamp: str = field(default="")

    def record(
        self,
        agent_name: str,
        data: dict[str, Any],
        timestamp: str,
        hand_off: str,
        called_from: str,
    ) -> None:
        """Record an agent run and update the state with the agent's output."""
        try:
            record = AgentRunRecord(
                agent=agent_name,
                data=data.copy(),
                timestamp=timestamp,
                hand_off=hand_off,
                called_from=called_from,
            )
            self.history.append(record)

            for key, value in data.items():
                self.set_variable(f"{agent_name}.{key}", value)
            self.set_variable(FLOCK_LAST_RESULT, data)
            self.set_variable(FLOCK_LAST_AGENT, agent_name)
        except Exception:
            raise

    def get_variable(self, key: str) -> Any:
        """Get the current value of a state variable."""
        try:
            return self.state.get(key)
        except Exception:
            raise

    def set_variable(self, key: str, value: Any) -> None:
        """Set the value of a state variable."""
        try:
            self.state[key] = value
        except Exception:
            raise

    def deepcopy(self) -> "FlockContext":
        """Create a deep copy of the context."""
        try:
            return FlockContext.from_dict(self.to_dict())
        except Exception:
            raise

    def get_agent_history(self, agent_name: str) -> list[AgentRunRecord]:
        """Return all agent run records for a given agent name."""
        try:
            return [
                record for record in self.history if record.agent == agent_name
            ]
        except Exception:
            raise

    def next_input_for(self, agent) -> Any:
        """By default, the next input for an agent is taken from the context state.

        If the agent.input is a comma-separated list (e.g., "input1, input2"),
        this method will return a dictionary with keys for each of the input names,
        fetching the latest values from the state.

        If only a single input is specified, the raw value is returned.
        """
        try:
            if hasattr(agent, "input") and isinstance(agent.input, str):
                keys = [k.strip() for k in agent.input.split(",") if k.strip()]

                if len(keys) == 1:
                    return self.get_variable(keys[0])
                else:
                    return {key: self.get_variable(key) for key in keys}
            else:
                # Fallback to "init_input"
                return self.get_variable("init_input")
        except Exception:
            raise

    def get_most_recent_value(self, variable_name: str) -> Any:
        """Get the definition for a specific agent."""
        try:
            for history_record in reversed(self.history):
                if variable_name in history_record.data:
                    return history_record.data[variable_name]
        except Exception:
            raise

    def get_agent_definition(self, agent_name: str) -> AgentDefinition | None:
        """Get the definition for a specific agent."""
        try:
            for definition in self.agent_definitions:
                if definition.name == agent_name:
                    return definition
            return None
        except Exception:
            raise

    def add_agent_definition(
        self, agent_type: type, agent_name: str, agent_data: Any
    ) -> None:
        """Add a new agent definition to the context."""
        try:
            definition = AgentDefinition(
                agent_type=agent_type.__name__,
                agent_name=agent_name,
                agent_data=agent_data,
            )
            self.agent_definitions[agent_name] = definition
        except Exception:
            raise

    # Allow dict-like access for convenience.
    def __getitem__(self, key: str) -> Any:
        """Get the current value of a state variable."""
        value = self.state[key]
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        """Set the value of a state variable."""
        self.state[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Convert the context to a dictionary for serialization."""
        try:

            def convert(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if hasattr(obj, "__dataclass_fields__"):  # Is a dataclass
                    return asdict(
                        obj,
                        dict_factory=lambda x: {k: convert(v) for k, v in x},
                    )
                return obj

            return convert(asdict(self))
        except Exception:
            raise

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlockContext":
        """Create a context instance from a dictionary."""
        try:

            def convert(obj):
                if isinstance(obj, dict):
                    if "timestamp" in obj:  # AgentRunRecord
                        return AgentRunRecord(
                            **{
                                **obj,
                                "timestamp": datetime.fromisoformat(
                                    obj["timestamp"]
                                ),
                            }
                        )
                    if "agent_type" in obj:  # AgentDefinition
                        return AgentDefinition(**obj)
                    return {k: convert(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [convert(v) for v in obj]
                return obj

            converted = convert(data)
            return cls(**converted)
        except Exception:
            raise
