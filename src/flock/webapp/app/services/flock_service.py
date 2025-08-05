# src/flock/webapp/app/services/flock_service.py
from typing import TYPE_CHECKING, Any, Optional

import yaml

# Conditional import for Flock and FlockFactory for type hinting
if TYPE_CHECKING:
    from flock.core.flock import Flock
    from flock.core.flock_factory import FlockFactory
else:
    Flock = "flock.core.flock.Flock"
    FlockFactory = "flock.core.flock_factory.FlockFactory"

from flock.core.api.run_store import RunStore
from flock.core.flock_registry import get_registry
from flock.core.logging.logging import get_logger
from flock.webapp.app.config import FLOCK_FILES_DIR
from flock.webapp.app.dependencies import set_global_flock_services

logger = get_logger("webapp.service")


def get_available_flock_files() -> list[str]:
    """Returns a sorted list of available .yaml, .yml, or .flock files."""
    if not FLOCK_FILES_DIR.exists():
        return []
    return sorted(
        [
            f.name
            for f in FLOCK_FILES_DIR.iterdir()
            if f.is_file() and (f.suffix.lower() in [".yaml", ".yml", ".flock"])
        ]
    )

def _ensure_run_store_in_app_state(app_state: object) -> RunStore: # app_state is Starlette's State
    """Ensures a RunStore instance exists in app_state, creating if necessary."""
    run_store = getattr(app_state, 'run_store', None)
    if not isinstance(run_store, RunStore):
        logger.info("RunStore not found or invalid in app_state, creating a new one for this session.")
        run_store = RunStore()
        setattr(app_state, 'run_store', run_store)
    return run_store


def load_flock_from_file_service(filename: str, app_state: object) -> Optional["Flock"]:
    """Loads a Flock instance from a file.
    Updates app_state with the loaded flock/filename and updates DI services.
    """
    from flock.core.flock import Flock as ConcreteFlock

    file_path = FLOCK_FILES_DIR / filename
    if not file_path.exists():
        logger.error(f"Flock file not found: {file_path}")
        clear_current_flock_service(app_state)
        return None
    try:
        logger.info(f"Loading flock from: {file_path}")
        loaded_flock = ConcreteFlock.load_from_file(str(file_path))

        setattr(app_state, 'flock_instance', loaded_flock)
        setattr(app_state, 'flock_filename', filename)
        run_store = _ensure_run_store_in_app_state(app_state)
        set_global_flock_services(loaded_flock, run_store)

        logger.info(f"Service: Successfully loaded flock '{loaded_flock.name}' from '{filename}'. DI updated.")
        return loaded_flock
    except Exception as e:
        logger.error(f"Service: Error loading flock from {file_path}: {e}", exc_info=True)
        clear_current_flock_service(app_state)
        return None


def create_new_flock_service(
    name: str, model: str | None, description: str | None, app_state: object
) -> "Flock":
    """Creates a new Flock instance.
    Updates app_state and DI services.
    """
    from flock.core.flock import Flock as ConcreteFlock

    effective_model = model.strip() if model and model.strip() else None
    new_flock = ConcreteFlock(
        name=name,
        model=effective_model,
        description=description,
        show_flock_banner=False,
    )
    default_filename = f"{name.replace(' ', '_').lower()}.flock.yaml"

    setattr(app_state, 'flock_instance', new_flock)
    setattr(app_state, 'flock_filename', default_filename)
    run_store = _ensure_run_store_in_app_state(app_state)
    set_global_flock_services(new_flock, run_store)

    logger.info(f"Service: Created new flock '{name}'. DI updated. Default filename: '{default_filename}'.")
    return new_flock


def clear_current_flock_service(app_state: object):
    """Clears the current Flock from app_state and updates DI services.
    """
    if hasattr(app_state, 'flock_instance'):
        delattr(app_state, 'flock_instance')
    if hasattr(app_state, 'flock_filename'):
        delattr(app_state, 'flock_filename')

    run_store = _ensure_run_store_in_app_state(app_state)
    set_global_flock_services(None, run_store)
    logger.info("Service: Current flock cleared from app_state. DI updated (Flock is None).")


def save_current_flock_to_file_service(new_filename: str, app_state: object) -> tuple[bool, str]:
    """Saves the Flock from app_state to a file. Updates app_state's current filename on success.
    """
    current_flock: Flock | None = getattr(app_state, 'flock_instance', None)
    if not current_flock:
        return False, "No flock loaded to save."
    if not new_filename.strip():
        return False, "Filename cannot be empty."

    save_path = FLOCK_FILES_DIR / new_filename
    try:
        current_flock.to_yaml_file(str(save_path))
        setattr(app_state, 'flock_filename', new_filename) # Update filename in app_state
        logger.info(f"Service: Flock '{current_flock.name}' saved to '{new_filename}'.")
        return True, f"Flock saved to '{new_filename}'."
    except Exception as e:
        logger.error(f"Service: Error saving flock '{current_flock.name}' to {save_path}: {e}", exc_info=True)
        return False, f"Error saving flock: {e}"


def update_flock_properties_service(
    name: str, model: str | None, description: str | None, app_state: object
) -> bool:
    """Updates properties of the Flock in app_state. Updates app_state's filename if name changes.
    """
    current_flock: Flock | None = getattr(app_state, 'flock_instance', None)
    current_filename: str | None = getattr(app_state, 'flock_filename', None)

    if not current_flock:
        logger.warning("Service: Attempted to update properties, but no flock loaded.")
        return False

    old_name = current_flock.name
    old_name_default_filename = f"{old_name.replace(' ', '_').lower()}.flock.yaml"

    current_flock.name = name
    current_flock.model = model.strip() if model and model.strip() else None
    current_flock.description = description

    if current_filename == old_name_default_filename and old_name != name:
        new_default_filename = f"{name.replace(' ', '_').lower()}.flock.yaml"
        setattr(app_state, 'flock_filename', new_default_filename)
        logger.info(f"Service: Default filename updated to '{new_default_filename}' due to flock name change.")

    logger.info(f"Service: Flock properties updated for '{name}'.")
    return True


def add_agent_to_current_flock_service(agent_config: dict, app_state: object) -> bool:
    """Adds an agent to the Flock in app_state."""
    from flock.core.flock_factory import FlockFactory as ConcreteFlockFactory

    current_flock: Flock | None = getattr(app_state, 'flock_instance', None)
    if not current_flock:
        logger.warning("Service: Cannot add agent, no flock loaded.")
        return False

    registry = get_registry()
    tools_instances = []
    if agent_config.get("tools_names"):
        for tool_name in agent_config["tools_names"]:
            try: tools_instances.append(registry.get_callable(tool_name))
            except KeyError: logger.warning(f"Service: Tool '{tool_name}' not found for agent '{agent_config['name']}'.")
    try:
        agent = ConcreteFlockFactory.create_default_agent(
            name=agent_config["name"],
            description=agent_config.get("description"),
            model=agent_config.get("model"),
            input=agent_config["input"],
            output=agent_config["output"],
            tools=tools_instances or None,
        )
        current_flock.add_agent(agent)
        logger.info(f"Service: Agent '{agent.name}' added to flock '{current_flock.name}'.")
        return True
    except Exception as e:
        logger.error(f"Service: Error adding agent to flock '{current_flock.name}': {e}", exc_info=True)
        return False


def update_agent_in_current_flock_service(
    original_agent_name: str, agent_config: dict, app_state: object
) -> bool:
    """Updates an agent in the Flock in app_state."""
    current_flock: Flock | None = getattr(app_state, 'flock_instance', None)
    if not current_flock:
        logger.warning("Service: Cannot update agent, no flock loaded.")
        return False

    agent_to_update = current_flock.agents.get(original_agent_name)
    if not agent_to_update:
        logger.warning(f"Service: Agent '{original_agent_name}' not found in flock '{current_flock.name}' for update.")
        return False

    registry = get_registry()
    tools_instances = []
    if agent_config.get("tools_names"):
        for tool_name in agent_config["tools_names"]:
            try: tools_instances.append(registry.get_callable(tool_name))
            except KeyError: logger.warning(f"Service: Tool '{tool_name}' not found during agent update.")
    try:
        new_name = agent_config["name"]
        agent_to_update.description = agent_config.get("description")
        current_agent_model = agent_config.get("model")
        agent_to_update.model = current_agent_model if current_agent_model and current_agent_model.strip() else None
        agent_to_update.input = agent_config["input"]
        agent_to_update.output = agent_config["output"]
        agent_to_update.tools = tools_instances or []

        if original_agent_name != new_name:
            current_flock._agents.pop(original_agent_name)
            agent_to_update.name = new_name
            current_flock.add_agent(agent_to_update)
            logger.info(f"Service: Agent '{original_agent_name}' renamed to '{new_name}' and updated in flock '{current_flock.name}'.")
        else:
            logger.info(f"Service: Agent '{original_agent_name}' updated in flock '{current_flock.name}'.")
        return True
    except Exception as e:
        logger.error(f"Service: Error updating agent '{original_agent_name}' in flock '{current_flock.name}': {e}", exc_info=True)
        return False


def remove_agent_from_current_flock_service(agent_name: str, app_state: object) -> bool:
    """Removes an agent from the Flock in app_state."""
    current_flock: Flock | None = getattr(app_state, 'flock_instance', None)
    if not current_flock or agent_name not in current_flock.agents:
        logger.warning(f"Service: Cannot remove agent '{agent_name}', no flock loaded or agent not found.")
        return False
    try:
        del current_flock._agents[agent_name]
        logger.info(f"Service: Agent '{agent_name}' removed from flock '{current_flock.name}'.")
        return True
    except Exception as e:
        logger.error(f"Service: Error removing agent '{agent_name}' from flock '{current_flock.name}': {e}", exc_info=True)
        return False


async def run_current_flock_service(
    start_agent_name: str,
    inputs: dict[str, Any],
    app_state: Any,
) -> dict[str, Any]:
    """Runs the specified agent from the current flock instance in app_state."""
    logger.info(f"Attempting to run agent: {start_agent_name} using flock from app_state.")

    current_flock: Flock | None = getattr(app_state, "flock_instance", None)
    run_store: RunStore | None = getattr(app_state, "run_store", None)

    if not current_flock:
        logger.error("Run service: No Flock instance available in app_state.")
        return {"error": "No Flock loaded in the application."}
    if not run_store:
        logger.error("Run service: No RunStore instance available in app_state.")
        # Attempt to initialize a default run_store if missing and this service is critical
        # This might indicate an issue in the application lifecycle setup
        logger.warning("Run service: Initializing a default RunStore as none was found in app_state.")
        run_store = RunStore()
        setattr(app_state, "run_store", run_store)
        # Also update global DI if this is how it's managed elsewhere for consistency,
        # though ideally DI setup handles this more centrally.
        # from flock.webapp.app.dependencies import set_global_flock_services
        # set_global_flock_services(current_flock, run_store)


    if start_agent_name not in current_flock.agents:
        logger.error(f"Run service: Agent '{start_agent_name}' not found in current flock '{current_flock.name}'.")
        return {"error": f"Agent '{start_agent_name}' not found."}

    try:
        logger.info(f"Executing agent '{start_agent_name}' from flock '{current_flock.name}' using app_state.")
        # Direct execution using the flock from app_state
        result = await current_flock.run_async(
            agent=start_agent_name, input=inputs, box_result=False
        )
        # Store run details using the run_store from app_state
        if hasattr(run_store, "add_run_details"): # Check if RunStore has this method
            run_id = result.get("run_id", "unknown_run_id") # Assuming run_async result might contain run_id
            run_store.add_run_details(run_id=run_id, agent_name=start_agent_name, inputs=inputs, outputs=result)
        return result
    except Exception as e:
        logger.error(f"Run service: Error during agent execution: {e}", exc_info=True)
        return {"error": f"An error occurred: {e}"}


def get_registered_items_service(item_type: str) -> list[dict]:
    """Retrieves items of a specific type from the global FlockRegistry."""
    registry = get_registry()
    items_dict: dict | None = None
    if item_type == "type":      items_dict = registry._types
    elif item_type == "tool":    items_dict = registry._callables
    elif item_type == "component": items_dict = registry._components
    else: return []

    if items_dict is None: return []

    items = []
    for name, item_obj in items_dict.items():
        module_path = "N/A"
        try: module_path = item_obj.__module__
        except AttributeError: pass
        items.append({"name": name, "module": module_path})
    return sorted(items, key=lambda x: x["name"])


def get_flock_preview_service(filename: str) -> dict | None:
    """Loads basic properties of a flock file for preview."""
    file_path = FLOCK_FILES_DIR / filename
    if not file_path.exists():
        logger.warning(f"Service: Preview failed, file not found {file_path}")
        return None
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return {
                    "name": data.get("name", filename),
                    "model": data.get("model"),
                    "description": data.get("description"),
                    "agents_count": len(data.get("agents", {})),
                    "enable_temporal": data.get("enable_temporal", False)
                }
        logger.warning(f"Service: Preview failed, '{filename}' is not a valid Flock YAML (not a dict).")
        return {"name": filename, "error": "Not a valid Flock YAML structure"}
    except Exception as e:
        logger.error(f"Service: Error getting flock preview for {filename}: {e}", exc_info=True)
        return {"name": filename, "error": str(e)}
