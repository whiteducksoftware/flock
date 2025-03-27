import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal

from opentelemetry import trace
from pydantic import BaseModel, Field

from flock.core.context.context_vars import FLOCK_LAST_AGENT, FLOCK_LAST_RESULT
from flock.core.logging.logging import get_logger
from flock.core.serialization.serializable import Serializable

logger = get_logger("context")
tracer = trace.get_tracer(__name__)


class AgentRunRecord(BaseModel):
    id: str = Field(default="")
    agent: str = Field(default="")
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default="")
    hand_off: dict | None = Field(default_factory=dict)
    called_from: str = Field(default="")


class AgentDefinition(BaseModel):
    agent_type: str = Field(default="")
    agent_name: str = Field(default="")
    agent_data: dict = Field(default_factory=dict)
    serializer: Literal["json", "cloudpickle", "msgpack"] = Field(
        default="cloudpickle"
    )


class FlockContext(Serializable, BaseModel):
    state: dict[str, Any] = Field(default_factory=dict)
    history: list[AgentRunRecord] = Field(default_factory=list)
    agent_definitions: dict[str, AgentDefinition] = Field(default_factory=dict)
    run_id: str = Field(default="")
    workflow_id: str = Field(default="")
    workflow_timestamp: str = Field(default="")

    def record(
        self,
        agent_name: str,
        data: dict[str, Any],
        timestamp: str,
        hand_off: str,
        called_from: str,
    ) -> None:
        record = AgentRunRecord(
            id=agent_name + "_" + uuid.uuid4().hex[:4],
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
        logger.info(
            f"Agent run recorded - run_id '{record.id}'",
            agent=agent_name,
            timestamp=timestamp,
            data=data,
        )
        current_span = trace.get_current_span()
        if current_span.get_span_context().is_valid:
            current_span.add_event(
                "record",
                attributes={"agent": agent_name, "timestamp": timestamp},
            )

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    def set_variable(self, key: str, value: Any) -> None:
        old_value = self.state.get(key)
        self.state[key] = value
        if old_value != value:
            escaped_value = str(value).replace("{", "{{").replace("}", "}}")

            logger.info(
                "Context variable updated - {} -> {}",
                key,
                escaped_value,  # Arguments in order
            )

            current_span = trace.get_current_span()
            if current_span.get_span_context().is_valid:
                current_span.add_event(
                    "set_variable",
                    attributes={
                        "key": key,
                        "old": str(old_value),
                        "new": str(value),
                    },
                )

    def deepcopy(self) -> "FlockContext":
        return FlockContext.from_dict(self.to_dict())

    def get_agent_history(self, agent_name: str) -> list[AgentRunRecord]:
        return [record for record in self.history if record.agent == agent_name]

    def next_input_for(self, agent) -> Any:
        try:
            if hasattr(agent, "input") and isinstance(agent.input, str):
                keys = [k.strip() for k in agent.input.split(",") if k.strip()]
                if len(keys) == 1:
                    return self.get_variable(keys[0])
                else:
                    return {key: self.get_variable(key) for key in keys}
            else:
                return self.get_variable("init_input")
        except Exception as e:
            logger.error(
                "Error getting next input for agent",
                agent=agent.name,
                error=str(e),
            )
            raise

    def get_most_recent_value(self, variable_name: str) -> Any:
        for history_record in reversed(self.history):
            if variable_name in history_record.data:
                return history_record.data[variable_name]

    def get_agent_definition(self, agent_name: str) -> AgentDefinition | None:
        return self.agent_definitions.get(agent_name)

    def add_agent_definition(
        self, agent_type: type, agent_name: str, agent_data: Any
    ) -> None:
        definition = AgentDefinition(
            agent_type=agent_type.__name__,
            agent_name=agent_name,
            agent_data=agent_data,
        )
        self.agent_definitions[agent_name] = definition

    # Use the reactive setter for dict-like access.
    def __getitem__(self, key: str) -> Any:
        return self.get_variable(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set_variable(key, value)

    def to_dict(self) -> dict[str, Any]:
        def convert(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, "__dataclass_fields__"):
                return asdict(
                    obj, dict_factory=lambda x: {k: convert(v) for k, v in x}
                )
            return obj

        return convert(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlockContext":
        def convert(obj):
            if isinstance(obj, dict):
                if "timestamp" in obj:
                    return AgentRunRecord(
                        **{
                            **obj,
                            "timestamp": datetime.fromisoformat(
                                obj["timestamp"]
                            ),
                        }
                    )
                if "agent_type" in obj:
                    return AgentDefinition(**obj)
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert(v) for v in obj]
            return obj

        converted = convert(data)
        return cls(**converted)
