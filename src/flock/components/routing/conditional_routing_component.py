# src/flock/components/routing/conditional_routing_component.py
"""Conditional routing component implementation for the unified component architecture."""

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from flock.core.component.agent_component_base import AgentComponentConfig
from flock.core.component.routing_component import RoutingComponent
from flock.core.context.context import FlockContext

# HandOffRequest removed - using agent.next_agent directly
from flock.core.logging.logging import get_logger
from flock.core.registry import flock_component, get_registry

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent

logger = get_logger("components.routing.conditional")


class ConditionalRoutingConfig(AgentComponentConfig):
    """Configuration for the ConditionalRoutingComponent."""

    condition_context_key: str = Field(
        default="flock.condition",
        description="Context key containing the value to evaluate the condition against.",
    )

    # --- Define ONE type of condition check ---
    condition_callable: (
        str | Callable[[Any], tuple[bool, str | None]] | None
    ) = Field(
        default=None,
        description="A callable (or registered name) that takes the context value and returns a tuple containing: (bool: True if condition passed, False otherwise, Optional[str]: Feedback message if condition failed).",
    )
    # String Checks
    expected_string: str | None = Field(
        default=None, description="String value to compare against."
    )
    string_mode: Literal[
        "equals",
        "contains",
        "regex",
        "startswith",
        "endswith",
        "not_equals",
        "not_contains",
    ] = Field(default="equals", description="How to compare strings.")
    ignore_case: bool = Field(
        default=True, description="Ignore case during string comparison."
    )
    # Length Checks (String or List)
    min_length: int | None = Field(
        default=None,
        description="Minimum length for strings or items for lists.",
    )
    max_length: int | None = Field(
        default=None,
        description="Maximum length for strings or items for lists.",
    )
    # Number Checks
    expected_number: int | float | None = Field(
        default=None, description="Number to compare against."
    )
    number_mode: Literal["<", "<=", "==", "!=", ">=", ">"] = Field(
        default="==", description="How to compare numbers."
    )
    # List Checks
    min_items: int | None = Field(
        default=None, description="Minimum number of items in a list."
    )
    max_items: int | None = Field(
        default=None, description="Maximum number of items in a list."
    )
    # Type Check
    expected_type_name: str | None = Field(
        default=None,
        description="Registered name of the expected Python type (e.g., 'str', 'list', 'MyCustomType').",
    )
    # Boolean Check
    expected_bool: bool | None = Field(
        default=None, description="Expected boolean value (True or False)."
    )
    # Existence Check
    check_exists: bool | None = Field(
        default=None,
        description="If True, succeeds if key exists; if False, succeeds if key *doesn't* exist. Ignores value.",
    )

    # --- Routing Targets ---
    success_agent: str | None = Field(
        default=None,
        description="Agent name to route to if the condition evaluates to True.",
    )
    failure_agent: str | None = Field(
        default=None,
        description="Agent name to route to if the condition evaluates to False (after retries, if enabled).",
    )
    retry_agent: str | None = Field(
        default=None,
        description="Agent name to route to if the condition evaluates to False (during retries, if enabled).",
    )

    # --- Optional Retry Logic (for Failure Path) ---
    retry_on_failure: bool = Field(
        default=False,
        description="If True, route back to the retry_agent on failure before going to failure_agent.",
    )
    max_retries: int = Field(
        default=1,
        description="Maximum number of times to retry the current agent on failure.",
    )
    feedback_context_key: str | None = Field(
        default="flock.assertion_feedback",  # Useful if paired with AssertionCheckerModule
        description="Optional context key containing feedback message to potentially include when retrying.",
    )
    retry_count_context_key_prefix: str = Field(
        default="flock.conditional_retry_count_",
        description="Internal prefix for context key storing retry attempts per agent.",
    )

    # --- Validator to ensure only one condition type is set ---
    @model_validator(mode="after")
    def check_exclusive_condition(self) -> "ConditionalRoutingConfig":
        conditions_set = [
            self.condition_callable is not None,
            self.expected_string is not None
            or self.min_length is not None
            or self.max_length is not None,  # String/Length group
            self.expected_number is not None,  # Number group
            self.min_items is not None
            or self.max_items is not None,  # List size group
            self.expected_type_name is not None,  # Type group
            self.expected_bool is not None,  # Bool group
            self.check_exists is not None,  # Existence group
        ]
        if sum(conditions_set) > 1:
            raise ValueError(
                "Only one type of condition (callable, string/length, number, list size, type, boolean, exists) can be configured per ConditionalRoutingComponent."
            )
        if sum(conditions_set) == 0:
            raise ValueError(
                "At least one condition type must be configured for ConditionalRoutingComponent."
            )
        return self


@flock_component(config_class=ConditionalRoutingConfig)
class ConditionalRoutingComponent(RoutingComponent):
    """Routes workflow based on evaluating a condition against a value in the FlockContext.
    
    Supports various built-in checks (string, number, list, type, bool, existence)
    or a custom callable. Can optionally retry the current agent on failure.
    """

    config: ConditionalRoutingConfig = Field(
        default_factory=ConditionalRoutingConfig
    )

    def __init__(
        self,
        name: str = "conditional_router",
        config: ConditionalRoutingConfig | None = None,
        **data,
    ):
        if config is None:
            config = ConditionalRoutingConfig()
        super().__init__(name=name, config=config, **data)

    def _evaluate_condition(self, value: Any) -> tuple[bool, str | None]:
        """Evaluates the condition based on the router's configuration.

        Returns:
            Tuple[bool, Optional[str]]: A tuple containing:
                - bool: True if the condition passed, False otherwise.
                - Optional[str]: A feedback message if the condition failed, otherwise None.
        """
        cfg = self.config
        condition_passed = False
        feedback = None  # Default feedback
        condition_type = "unknown"

        try:
            # 0. Check Existence first (simplest)
            if cfg.check_exists is not None:
                condition_type = "existence"
                value_exists = value is not None
                condition_passed = (
                    value_exists if cfg.check_exists else not value_exists
                )
                if not condition_passed:
                    feedback = f"Existence check failed: Expected key '{cfg.condition_context_key}' to {'exist' if cfg.check_exists else 'not exist or be None'}, but it was {'found' if value_exists else 'missing/None'}."

            # 1. Custom Callable
            elif cfg.condition_callable:
                condition_type = "callable"
                callable_func = cfg.condition_callable
                if isinstance(callable_func, str):  # Lookup registered callable
                    registry = get_registry()
                    try:
                        callable_func = registry.get_callable(callable_func)
                    except KeyError:
                        feedback = f"Condition callable '{cfg.condition_callable}' not found in registry."
                        logger.error(feedback)
                        return False, feedback  # Treat as failure

                if callable(callable_func):
                    eval_result = callable_func(value)
                    if (
                        isinstance(eval_result, tuple)
                        and len(eval_result) == 2
                        and isinstance(eval_result[0], bool)
                    ):
                        condition_passed, custom_feedback = eval_result
                        if not condition_passed and isinstance(
                            custom_feedback, str
                        ):
                            feedback = custom_feedback
                    elif isinstance(eval_result, bool):
                        condition_passed = eval_result
                        if not condition_passed:
                            feedback = f"Callable condition '{getattr(callable_func, '__name__', 'anonymous')}' returned False."
                    else:
                        feedback = f"Condition callable '{getattr(callable_func, '__name__', 'anonymous')}' returned unexpected type: {type(eval_result)}."
                        logger.warning(feedback)
                        return False, feedback  # Treat as failure
                else:
                    feedback = f"Configured condition_callable '{cfg.condition_callable}' is not callable."
                    logger.error(feedback)
                    return False, feedback

            # 2. String / Length Checks
            elif (
                cfg.expected_string is not None
                or cfg.min_length is not None
                or cfg.max_length is not None
            ):
                condition_type = "string/length"
                if not isinstance(value, str):
                    feedback = f"Cannot perform string/length check on non-string value: {type(value)}."
                    logger.warning(feedback)
                    return False, feedback
                s_value = value
                val_len = len(s_value)
                length_passed = True
                length_feedback = []
                if cfg.min_length is not None and val_len < cfg.min_length:
                    length_passed = False
                    length_feedback.append(
                        f"length {val_len} is less than minimum {cfg.min_length}"
                    )
                if cfg.max_length is not None and val_len > cfg.max_length:
                    length_passed = False
                    length_feedback.append(
                        f"length {val_len} is greater than maximum {cfg.max_length}"
                    )

                content_passed = True
                content_feedback = ""
                if cfg.expected_string is not None:
                    expected = cfg.expected_string
                    s1 = s_value if not cfg.ignore_case else s_value.lower()
                    s2 = expected if not cfg.ignore_case else expected.lower()
                    mode = cfg.string_mode
                    if mode == "equals":
                        content_passed = s1 == s2
                    elif mode == "contains":
                        content_passed = s2 in s1
                    elif mode == "startswith":
                        content_passed = s1.startswith(s2)
                    elif mode == "endswith":
                        content_passed = s1.endswith(s2)
                    elif mode == "not_equals":
                        content_passed = s1 != s2
                    elif mode == "not_contains":
                        content_passed = s2 not in s1
                    elif mode == "regex":
                        content_passed = bool(re.search(expected, value))
                    else:
                        content_passed = False
                    if not content_passed:
                        content_feedback = f"String content check '{mode}' failed against expected '{expected}' (ignore_case={cfg.ignore_case})."

                condition_passed = length_passed and content_passed
                if not condition_passed:
                    feedback_parts = length_feedback + (
                        [content_feedback] if content_feedback else []
                    )
                    feedback = (
                        "; ".join(feedback_parts)
                        if feedback_parts
                        else "String/length condition failed."
                    )

            # 3. Number Check
            elif cfg.expected_number is not None:
                condition_type = "number"
                if not isinstance(value, (int, float)):
                    feedback = f"Cannot perform number check on non-numeric value: {type(value)}."
                    logger.warning(feedback)
                    return False, feedback
                num_value = value
                expected = cfg.expected_number
                mode = cfg.number_mode
                op_map = {
                    "<": lambda a, b: a < b,
                    "<=": lambda a, b: a <= b,
                    "==": lambda a, b: a == b,
                    "!=": lambda a, b: a != b,
                    ">=": lambda a, b: a >= b,
                    ">": lambda a, b: a > b,
                }
                if mode in op_map:
                    condition_passed = op_map[mode](num_value, expected)
                    if not condition_passed:
                        feedback = f"Number check failed: {num_value} {mode} {expected} is false."
                else:
                    condition_passed = False
                    feedback = f"Invalid number comparison mode: {mode}"

            # 4. List Size Check
            elif cfg.min_items is not None or cfg.max_items is not None:
                condition_type = "list size"
                if not isinstance(value, list):
                    feedback = f"Cannot perform list size check on non-list value: {type(value)}."
                    logger.warning(feedback)
                    return False, feedback
                list_len = len(value)
                size_passed = True
                size_feedback = []
                if cfg.min_items is not None and list_len < cfg.min_items:
                    size_passed = False
                    size_feedback.append(
                        f"list size {list_len} is less than minimum {cfg.min_items}"
                    )
                if cfg.max_items is not None and list_len > cfg.max_items:
                    size_passed = False
                    size_feedback.append(
                        f"list size {list_len} is greater than maximum {cfg.max_items}"
                    )
                condition_passed = size_passed
                if not condition_passed:
                    feedback = "; ".join(size_feedback)

            # 5. Type Check
            elif cfg.expected_type_name is not None:
                condition_type = "type"
                registry = get_registry()
                try:
                    expected_type = registry.get_type(cfg.expected_type_name)
                    condition_passed = isinstance(value, expected_type)
                    if not condition_passed:
                        feedback = f"Type check failed: Value type '{type(value).__name__}' is not instance of expected '{cfg.expected_type_name}'."
                except KeyError:
                    feedback = f"Expected type '{cfg.expected_type_name}' not found in registry."
                    logger.error(feedback)
                    return False, feedback

            # 6. Boolean Check
            elif cfg.expected_bool is not None:
                condition_type = "boolean"
                if not isinstance(value, bool):
                    feedback = f"Cannot perform boolean check on non-bool value: {type(value)}."
                    logger.warning(feedback)
                    return False, feedback
                condition_passed = value == cfg.expected_bool
                if not condition_passed:
                    feedback = f"Boolean check failed: Value '{value}' is not expected '{cfg.expected_bool}'."

            logger.debug(
                f"Condition check '{condition_type}' result: {condition_passed}"
            )
            return condition_passed, feedback if not condition_passed else None

        except Exception as e:
            feedback = (
                f"Error evaluating condition type '{condition_type}': {e}"
            )
            logger.error(feedback, exc_info=True)
            return (
                False,
                feedback,
            )  # Treat evaluation errors as condition failure

    async def determine_next_step(
        self,
        agent: "FlockAgent",
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Determine next step based on evaluating a condition against context value."""
        if not context:
            logger.warning("No context provided for conditional routing")
            return

        cfg = self.config
        condition_value = context.get_variable(cfg.condition_context_key, None)
        feedback_value = context.get_variable(cfg.feedback_context_key, None)

        logger.debug(
            f"Routing based on condition key '{cfg.condition_context_key}', value: {str(condition_value)[:100]}..."
        )

        # Evaluate the condition and get feedback on failure
        condition_passed, feedback_msg = self._evaluate_condition(
            condition_value
        )

        if condition_passed:
            # --- Success Path ---
            logger.info(
                f"Condition PASSED for agent '{agent.name}'. Routing to success path."
            )
            # Reset retry count if applicable
            if cfg.retry_on_failure:
                retry_key = (
                    f"{cfg.retry_count_context_key_prefix}{agent.name}"
                )
                if retry_key in context.state:
                    del context.state[retry_key]
                    logger.debug(
                        f"Reset retry count for agent '{agent.name}'."
                    )

            # Clear feedback from context on success
            if (
                cfg.feedback_context_key
                and cfg.feedback_context_key in context.state
            ):
                del context.state[cfg.feedback_context_key]
                logger.debug(
                    f"Cleared feedback key '{cfg.feedback_context_key}' on success."
                )

            next_agent = cfg.success_agent or None  # Stop chain if None
            logger.debug(f"Success route target: '{next_agent}'")

            agent.next_agent = next_agent  # Set directly on agent

        else:
            # --- Failure Path ---
            logger.warning(
                f"Condition FAILED for agent '{agent.name}'. Reason: {feedback_msg}"
            )

            if cfg.retry_on_failure:
                # --- Retry Logic ---
                retry_key = (
                    f"{cfg.retry_count_context_key_prefix}{agent.name}"
                )
                retry_count = context.get_variable(retry_key, 0)

                if retry_count < cfg.max_retries:
                    next_retry_count = retry_count + 1
                    context.set_variable(retry_key, next_retry_count)
                    logger.info(
                        f"Routing back to agent '{agent.name}' for retry #{next_retry_count}/{cfg.max_retries}."
                    )

                    # Add specific feedback to context if retry is enabled
                    if cfg.feedback_context_key:
                        context.set_variable(
                            cfg.feedback_context_key,
                            feedback_msg or "Condition failed",
                        )
                        logger.debug(
                            f"Set feedback key '{cfg.feedback_context_key}': {feedback_msg or 'Condition failed'}"
                        )

                    agent.next_agent = agent.name  # Route back to self
                else:
                    # --- Max Retries Exceeded ---
                    logger.error(
                        f"Max retries ({cfg.max_retries}) exceeded for agent '{agent.name}'."
                    )
                    if retry_key in context.state:
                        del context.state[retry_key]  # Reset count
                    next_agent = cfg.failure_agent or None
                    logger.debug(
                        f"Failure route target (after retries): '{next_agent}'"
                    )

                    agent.next_agent = next_agent
            else:
                # --- No Retry Logic ---
                next_agent = (
                    cfg.failure_agent or None
                )  # Use failure agent or stop
                logger.debug(f"Failure route target (no retry): '{next_agent}'")

                agent.next_agent = next_agent
