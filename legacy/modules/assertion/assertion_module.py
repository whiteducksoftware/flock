# src/flock/modules/asserts/assertion_module.py (New File)

import json
from collections.abc import Callable
from typing import Any, Literal

import dspy  # For potential LLM-based rule checking
from pydantic import BaseModel, Field, PrivateAttr, ValidationError

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_module import FlockModule, FlockModuleConfig

# Need registry access if rules are callables defined elsewhere
from flock.core.flock_registry import flock_component, get_registry
from flock.core.logging.logging import get_logger

logger = get_logger("module.assertion")

# --- Rule Definition ---
# Rules can be defined in several ways:
# 1. Python lambda/function: (result: Dict, inputs: Dict, context: FlockContext) -> bool | Tuple[bool, str]
# 2. String referencing a registered callable: "my_validation_function"
# 3. Natural language rule string: "The summary must contain the keyword 'Flock'." (requires LLM judge)
# 4. Pydantic Model: The output must conform to this Pydantic model.

RuleType = (
    Callable[[dict, dict, FlockContext | None], bool | tuple[bool, str]]
    | str
    | type[BaseModel]
)


class Rule(BaseModel):
    """Container for a single assertion rule."""

    condition: RuleType = Field(
        ...,
        description="""
# --- Rule Definition ---
# Rules can be defined in several ways:
# 1. Python lambda/function: (result: Dict, inputs: Dict, context: FlockContext) -> bool | Tuple[bool, str]
# 2. String referencing a registered callable: "my_validation_function"
# 3. Natural language rule string: "The summary must contain the keyword 'Flock'." (requires LLM judge)
# 4. Pydantic Model: The output must conform to this Pydantic model.
                                """,
    )
    fail_message: str  # Message to provide as feedback on failure
    name: str | None = None  # Optional name for clarity

    def __post_init__(self):
        # Basic validation of fail_message
        if not isinstance(self.fail_message, str) or not self.fail_message:
            raise ValueError("Rule fail_message must be a non-empty string.")


class AssertionModuleConfig(FlockModuleConfig):
    """--- Rule Definition ---
    Rules can be defined in several ways:
    1. Python lambda/function: (result: Dict, inputs: Dict, context: FlockContext) -> bool | Tuple[bool, str]
    2. String referencing a registered callable: "my_validation_function"
    3. Natural language rule string: "The summary must contain the keyword 'Flock'." (requires LLM judge)
    4. Pydantic Model: The output must conform to this Pydantic model.
    """

    rules: list[Rule] = Field(
        default_factory=list,
        description="List of rules to check against the agent's output.",
    )
    # Optional LLM for evaluating natural language rules
    judge_lm_model: str | None = Field(
        None, description="LLM model to use for judging natural language rules."
    )
    # How to handle failure
    on_failure: Literal["add_feedback", "raise_error", "log_warning"] = Field(
        default="add_feedback",
        description="Action on rule failure: 'add_feedback' to context, 'raise_error', 'log_warning'.",
    )
    feedback_context_key: str = Field(
        default="flock.assertion_feedback",
        description="Context key to store failure messages for retry loops.",
    )
    clear_feedback_on_success: bool = Field(
        default=True,
        description="Clear the feedback key from context if all assertions pass.",
    )


@flock_component(config_class=AssertionModuleConfig)
class AssertionCheckerModule(FlockModule):
    """Checks the output of an agent against a set of defined rules.

    Can trigger different actions on failure, including adding feedback
    to the context to enable self-correction loops via routing.
    """

    name: str = "assertion_checker"
    config: AssertionModuleConfig = Field(default_factory=AssertionModuleConfig)
    _judge_lm: dspy.LM | None = PrivateAttr(None)  # Initialize lazily

    def _get_judge_lm(self) -> dspy.LM | None:
        """Initializes the judge LM if needed."""
        if self.config.judge_lm_model and self._judge_lm is None:
            try:
                self._judge_lm = dspy.LM(self.config.judge_lm_model)
            except Exception as e:
                logger.error(
                    f"Failed to initialize judge LM '{self.config.judge_lm_model}': {e}"
                )
                # Proceed without judge LM for other rule types
        return self._judge_lm

    async def on_post_evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Checks rules after the main evaluator runs."""
        if not self.config.rules:
            return result  # No rules to check

        logger.debug(f"Running assertion checks for agent '{agent.name}'...")
        all_passed = True
        failed_messages = []
        registry = get_registry()  # Needed for callable lookup

        for i, rule in enumerate(self.config.rules):
            rule_name = rule.name or f"Rule_{i + 1}"
            passed = False
            eval_result = None
            feedback_msg = rule.fail_message

            try:
                condition = rule.condition
                if callable(condition):
                    # Rule is a Python function/lambda
                    logger.debug(f"Checking callable rule: {rule_name}")
                    eval_result = condition(result, inputs, context)
                elif isinstance(condition, str) and registry.contains(
                    condition
                ):
                    # Rule is a string referencing a registered callable
                    logger.debug(
                        f"Checking registered callable rule: '{condition}'"
                    )
                    rule_func = registry.get_callable(condition)
                    eval_result = rule_func(result, inputs, context)
                elif isinstance(condition, str):
                    # Rule is a natural language string (requires judge LLM)
                    logger.debug(
                        f"Checking natural language rule: '{condition}'"
                    )
                    judge_lm = self._get_judge_lm()
                    if judge_lm:
                        # Define a simple judge signature dynamically or use a predefined one
                        class JudgeSignature(dspy.Signature):
                            """Evaluate if the output meets the rule based on input and output."""

                            program_input: str = dspy.InputField(
                                desc="Input provided to the agent."
                            )
                            program_output: str = dspy.InputField(
                                desc="Output generated by the agent."
                            )
                            rule_to_check: str = dspy.InputField(
                                desc="The rule to verify."
                            )
                            is_met: bool = dspy.OutputField(
                                desc="True if the rule is met, False otherwise."
                            )
                            reasoning: str = dspy.OutputField(
                                desc="Brief reasoning for the decision."
                            )

                        judge_predictor = dspy.Predict(
                            JudgeSignature, llm=judge_lm
                        )
                        # Convert complex dicts/lists to strings for the judge prompt
                        input_str = json.dumps(inputs, default=str, indent=2)
                        result_str = json.dumps(result, default=str, indent=2)
                        judge_pred = judge_predictor(
                            program_input=input_str,
                            program_output=result_str,
                            rule_to_check=condition,
                        )
                        passed = judge_pred.is_met
                        feedback_msg = f"{rule.fail_message} (Reason: {judge_pred.reasoning})"
                        logger.debug(
                            f"LLM Judge result for rule '{condition}': {passed} ({judge_pred.reasoning})"
                        )
                    else:
                        logger.warning(
                            f"Cannot evaluate natural language rule '{condition}' - no judge_lm_model configured."
                        )
                        passed = True  # Default to pass if no judge available? Or fail? Let's pass.

                elif isinstance(condition, type) and issubclass(
                    condition, BaseModel
                ):
                    # Rule is a Pydantic model for validation
                    logger.debug(
                        f"Checking Pydantic validation rule: {condition.__name__}"
                    )
                    try:
                        # Assumes the *entire* result dict should match the model
                        # More specific logic might be needed (e.g., validate only a specific key)
                        condition.model_validate(result)
                        passed = True
                    except ValidationError as e:
                        passed = False
                        feedback_msg = (
                            f"{rule.fail_message} (Validation Error: {e})"
                        )
                else:
                    logger.warning(
                        f"Unsupported rule type for rule '{rule_name}': {type(condition)}"
                    )
                    continue  # Skip rule

                # Process result if it was a callable returning bool or (bool, msg)
                if eval_result is not None:
                    if (
                        isinstance(eval_result, tuple)
                        and len(eval_result) == 2
                        and isinstance(eval_result[0], bool)
                    ):
                        passed, custom_msg = eval_result
                        if not passed and custom_msg:
                            feedback_msg = (
                                custom_msg  # Use custom message on failure
                            )
                    elif isinstance(eval_result, bool):
                        passed = eval_result
                    else:
                        logger.warning(
                            f"Rule callable '{rule_name}' returned unexpected type: {type(eval_result)}. Rule skipped."
                        )
                        continue

                # Handle failure
                if not passed:
                    all_passed = False
                    failed_messages.append(feedback_msg)
                    logger.warning(
                        f"Assertion Failed for agent '{agent.name}': {feedback_msg}"
                    )
                    # Optionally break early? For now, check all rules.

            except Exception as e:
                logger.error(
                    f"Error executing rule '{rule_name}' for agent '{agent.name}': {e}",
                    exc_info=True,
                )
                all_passed = False
                failed_messages.append(
                    f"Error checking rule '{rule_name}': {e}"
                )
                # Treat error during check as failure

        # --- Take action based on results ---
        if not all_passed:
            logger.warning(f"Agent '{agent.name}' failed assertion checks.")
            if self.config.on_failure == "add_feedback" and context:
                context.set_variable(
                    self.config.feedback_context_key, "\n".join(failed_messages)
                )
                logger.debug(
                    f"Added assertion feedback to context key '{self.config.feedback_context_key}'"
                )
            elif self.config.on_failure == "raise_error":
                # Maybe wrap in a specific FlockAssertionError
                raise AssertionError(
                    f"Agent '{agent.name}' failed assertions: {'; '.join(failed_messages)}"
                )
            # else "log_warning" is default behavior
        elif context and self.config.clear_feedback_on_success:
            # Clear feedback key if all rules passed and key exists
            if self.config.feedback_context_key in context.state:
                del context.state[self.config.feedback_context_key]
                logger.debug(
                    f"Cleared assertion feedback key '{self.config.feedback_context_key}' on success."
                )

        return result  # Return the original result unmodified
