# src/flock/core/agent/flock_agent_serialization.py
"""Serialization functionality for FlockAgent."""

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

# Legacy component imports removed
from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_server import FlockMCPServer
from flock.core.serialization.json_encoder import FlockJSONEncoder
from flock.core.serialization.serialization_utils import (
    deserialize_component,
    serialize_item,
)

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent

logger = get_logger("agent.serialization")
T = TypeVar("T", bound="FlockAgent")


class FlockAgentSerialization:
    """Handles serialization and deserialization for FlockAgent."""

    def __init__(self, agent: "FlockAgent"):
        self.agent = agent

    def _save_output(self, agent_name: str, result: dict[str, Any]) -> None:
        """Save output to file if configured."""
        if not self.agent.config.write_to_file:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{agent_name}_output_{timestamp}.json"
        filepath = os.path.join(".flock/output/", filename)
        os.makedirs(".flock/output/", exist_ok=True)

        output_data = {
            "agent": agent_name,
            "timestamp": timestamp,
            "output": result,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(output_data, f, indent=2, cls=FlockJSONEncoder)
        except Exception as e:
            logger.warning(f"Failed to save output to file: {e}")

    def to_dict(self) -> dict[str, Any]:
        """Convert instance to dictionary representation suitable for serialization."""
        from flock.core.registry import get_registry

        registry = get_registry()

        exclude = [
            "context",
            "components",
            "tools",
            "servers",
        ]

        is_description_callable = False
        is_input_callable = False
        is_output_callable = False
        is_next_agent_callable = False
        # if self.agent.description is a callable, exclude it
        if callable(self.agent.description_spec):
            is_description_callable = True
            exclude.append("description_spec")
        # if self.agent.input is a callable, exclude it
        if callable(self.agent.input_spec):
            is_input_callable = True
            exclude.append("input_spec")
        # if self.agent.output is a callable, exclude it
        if callable(self.agent.output_spec):
            is_output_callable = True
            exclude.append("output_spec")
        if callable(self.agent.next_agent_spec):
            is_next_agent_callable = True
            exclude.append("next_agent_spec")

        logger.debug(f"Serializing agent '{self.agent.name}' to dict.")
        # Use Pydantic's dump, exclude manually handled fields and runtime context
        data = self.agent.model_dump(
            exclude=exclude,
            mode="json",  # Use json mode for better handling of standard types by Pydantic
            exclude_none=True,  # Exclude None values for cleaner output
        )
        logger.debug(f"Base agent data for '{self.agent.name}': {list(data.keys())}")

        # Serialize components list using unified architecture
        if self.agent.components:
            serialized_components = []
            for component in self.agent.components:
                try:
                    comp_type = type(component)
                    type_name = registry.get_component_type_name(comp_type)
                    if type_name:
                        component_data = serialize_item(component)
                        if isinstance(component_data, dict):
                            component_data["type"] = type_name
                            serialized_components.append(component_data)
                        else:
                            logger.warning(f"Component {component.name} serialization failed")
                    else:
                        logger.warning(f"Component {component.name} type not registered")
                except Exception as e:
                    logger.error(f"Failed to serialize component {component.name}: {e}")

            if serialized_components:
                data["components"] = serialized_components
                logger.debug(f"Added {len(serialized_components)} components to agent '{self.agent.name}'")

        # --- Serialize Servers ---
        if self.agent.servers:
            logger.debug(
                f"Serializing {len(self.agent.servers)} servers for agent '{self.agent.name}'"
            )
            serialized_servers = []
            for server in self.agent.servers:
                if isinstance(server, FlockMCPServer):
                    serialized_servers.append(server.config.name)
                else:
                    # Write it down as a list of server names.
                    serialized_servers.append(server)

            if serialized_servers:
                data["mcp_servers"] = serialized_servers
                logger.debug(
                    f"Added {len(serialized_servers)} servers to agent '{self.agent.name}'"
                )

        # --- Serialize Tools (Callables) ---
        if self.agent.tools:
            logger.debug(
                f"Serializing {len(self.agent.tools)} tools for agent '{self.agent.name}'"
            )
            serialized_tools = []
            for tool in self.agent.tools:
                if callable(tool) and not isinstance(tool, type):
                    path_str = registry.get_callable_path_string(tool)
                    if path_str:
                        # Get just the function name from the path string
                        # If it's a namespaced path like module.submodule.function_name
                        # Just use the function_name part
                        func_name = path_str.split(".")[-1]
                        serialized_tools.append(func_name)
                        logger.debug(
                            f"Added tool '{func_name}' (from path '{path_str}') to agent '{self.agent.name}'"
                        )
                    else:
                        logger.warning(
                            f"Could not get path string for tool {tool} in agent '{self.agent.name}'. Skipping."
                        )
                else:
                    logger.warning(
                        f"Non-callable item found in tools list for agent '{self.agent.name}': {tool}. Skipping."
                    )
            if serialized_tools:
                data["tools"] = serialized_tools
                logger.debug(
                    f"Added {len(serialized_tools)} tools to agent '{self.agent.name}'"
                )

        if is_description_callable:
            path_str = registry.get_callable_path_string(self.agent.description_spec)
            if path_str:
                func_name = path_str.split(".")[-1]
                data["description_callable"] = func_name
                logger.debug(
                    f"Added description '{func_name}' (from path '{path_str}') to agent '{self.agent.name}'"
                )
            else:
                logger.warning(
                    f"Could not get path string for description {self.agent.description_spec} in agent '{self.agent.name}'. Skipping."
                )

        if is_input_callable:
            path_str = registry.get_callable_path_string(self.agent.input_spec)
            if path_str:
                func_name = path_str.split(".")[-1]
                data["input_callable"] = func_name
                logger.debug(
                    f"Added input '{func_name}' (from path '{path_str}') to agent '{self.agent.name}'"
                )
            else:
                logger.warning(
                    f"Could not get path string for input {self.agent.input_spec} in agent '{self.agent.name}'. Skipping."
                )

        if is_output_callable:
            path_str = registry.get_callable_path_string(self.agent.output_spec)
            if path_str:
                func_name = path_str.split(".")[-1]
                data["output_callable"] = func_name
                logger.debug(
                    f"Added output '{func_name}' (from path '{path_str}') to agent '{self.agent.name}'"
                )
            else:
                logger.warning(
                    f"Could not get path string for output {self.agent.output_spec} in agent '{self.agent.name}'. Skipping."
                )

        if is_next_agent_callable:
            path_str = registry.get_callable_path_string(self.agent.next_agent_spec)
            if path_str:
                func_name = path_str.split(".")[-1]
                data["next_agent_callable"] = func_name
                logger.debug(
                    f"Added next_agent '{func_name}' (from path '{path_str}') to agent '{self.agent.name}'"
                )
            else:
                logger.warning(
                    f"Could not get path string for next_agent {self.agent.next_agent_spec} in agent '{self.agent.name}'. Skipping."
                )


        logger.info(
            f"Serialization of agent '{self.agent.name}' complete with {len(data)} fields"
        )
        return data

    @classmethod
    def from_dict(cls, agent_class: type[T], data: dict[str, Any]) -> T:
        """Deserialize the agent from a dictionary, including components, tools, and callables."""
        from flock.core.component.agent_component_base import AgentComponent
        from flock.core.registry import get_registry

        registry = get_registry()
        logger.debug(
            f"Deserializing agent from dict. Keys: {list(data.keys())}"
        )

        # --- Separate Data ---
        components_data = data.pop("components", [])
        callable_configs = {}
        tool_config = data.pop("tools", [])
        servers_config = data.pop("mcp_servers", [])

        callable_keys = [
            "description_callable",
            "input_callable",
            "output_callable",
            "next_agent_callable",
        ]

        for key in callable_keys:
            if key in data and data[key] is not None:
                callable_configs[key] = data.pop(key)

        # --- Deserialize Base Agent ---
        # Ensure required fields like 'name' are present if needed by __init__
        if "name" not in data:
            raise ValueError(
                "Agent data must include a 'name' field for deserialization."
            )
        agent_name_log = data["name"]  # For logging
        logger.info(f"Deserializing base agent data for '{agent_name_log}'")

        # Pydantic should handle base fields based on type hints in __init__
        agent = agent_class(**data)
        logger.debug(f"Base agent '{agent.name}' instantiated.")

        # --- Deserialize Components ---
        logger.debug(f"Deserializing components for '{agent.name}'")
        if components_data:
            for component_data in components_data:
                try:
                    # Use the existing deserialize_component function
                    component = deserialize_component(component_data, AgentComponent)
                    if component:
                        agent.add_component(component)
                        logger.debug(f"Deserialized and added component '{component.name}' for '{agent.name}'")
                except Exception as e:
                    logger.error(f"Failed to deserialize component: {e}")

        # --- Deserialize Tools ---
        agent.tools = []  # Initialize tools list
        if tool_config:
            logger.debug(
                f"Deserializing {len(tool_config)} tools for '{agent.name}'"
            )
            # Use get_callable to find each tool
            for tool_name_or_path in tool_config:
                try:
                    found_tool = registry.get_callable(tool_name_or_path)
                    if found_tool and callable(found_tool):
                        agent.tools.append(found_tool)
                        logger.debug(
                            f"Resolved and added tool '{tool_name_or_path}' for agent '{agent.name}'"
                        )
                    else:
                        # Should not happen if get_callable returns successfully but just in case
                        logger.warning(
                            f"Registry returned non-callable for tool '{tool_name_or_path}' for agent '{agent.name}'. Skipping."
                        )
                except (
                    ValueError
                ) as e:  # get_callable raises ValueError if not found/ambiguous
                    logger.warning(
                        f"Could not resolve tool '{tool_name_or_path}' for agent '{agent.name}': {e}. Skipping."
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error resolving tool '{tool_name_or_path}' for agent '{agent.name}': {e}. Skipping.",
                        exc_info=True,
                    )

        # --- Deserialize Servers ---
        agent.servers = []  # Initialize Servers list.
        if servers_config:
            logger.debug(
                f"Deserializing {len(servers_config)} servers for '{agent.name}'"
            )
            # Agents keep track of server by getting a list of server names.
            # The server instances will be retrieved during runtime from the registry. (default behavior)

            for server_name in servers_config:
                if isinstance(server_name, str):
                    # Case 1 (default behavior): A server name is passed.
                    agent.servers.append(server_name)
                elif isinstance(server_name, FlockMCPServer):
                    # Case 2 (highly unlikely): If someone somehow manages to pass
                    # an instance of a server during the deserialization step (however that might be achieved)
                    # check the registry, if the server is already registered, if not, register it
                    # and store the name in the servers list
                    server_exists = (
                        registry.get_server(server_name.config.name)
                        is not None
                    )
                    if server_exists:
                        agent.servers.append(server_name.config.name)
                    else:
                        registry.register_server(
                            server=server_name
                        )  # register it.
                        agent.servers.append(server_name.config.name)

        # --- Deserialize Callables ---
        logger.debug(f"Deserializing callable fields for '{agent.name}'")

        def resolve_and_assign(field_name: str, callable_key: str):
            if callable_key in callable_configs:
                callable_name = callable_configs[callable_key]
                try:
                    # Use get_callable to find the signature function
                    found_callable = registry.get_callable(callable_name)
                    if found_callable and callable(found_callable):
                        setattr(agent, field_name, found_callable)
                        logger.debug(
                            f"Resolved callable '{callable_name}' for field '{field_name}' on agent '{agent.name}'"
                        )
                    else:
                        logger.warning(
                            f"Registry returned non-callable for name '{callable_name}' for field '{field_name}' on agent '{agent.name}'. Field remains default."
                        )
                except (
                    ValueError
                ) as e:  # get_callable raises ValueError if not found/ambiguous
                    logger.warning(
                        f"Could not resolve callable '{callable_name}' in registry for field '{field_name}' on agent '{agent.name}': {e}. Field remains default."
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error resolving callable '{callable_name}' for field '{field_name}' on agent '{agent.name}': {e}. Field remains default.",
                        exc_info=True,
                    )
            # Else: key not present, field retains its default value from __init__

        resolve_and_assign("description", "description_callable")
        resolve_and_assign("input", "input_callable")
        resolve_and_assign("output", "output_callable")
        resolve_and_assign("next_agent", "next_agent_callable")
        # --- Finalize ---

        logger.info(f"Successfully deserialized agent '{agent.name}'.")
        return agent
