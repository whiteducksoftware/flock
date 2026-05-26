# src/flock/routers/correction/correction_router.py (New File)

from typing import Any

from pydantic import Field

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent
from flock.core.flock_registry import flock_component
from flock.core.flock_router import (
    FlockRouter,
    FlockRouterConfig,
    HandOffRequest,
)
from flock.core.logging.logging import get_logger

logger = get_logger("router.correction")


class FeedbackRetryRouterConfig(FlockRouterConfig):
    max_retries: int = Field(
        default=1,
        description="Maximum number of times to retry the same agent on failure.",
    )
    feedback_context_key: str = Field(
        default="flock.assertion_feedback",
        description="Context key containing feedback from AssertionCheckerModule.",
    )
    retry_count_context_key_prefix: str = Field(
        default="flock.retry_count_",
        description="Prefix for context key storing retry attempts per agent.",
    )
    fallback_agent: str | None = Field(
        None, description="Agent to route to if max_retries is exceeded."
    )


@flock_component(config_class=FeedbackRetryRouterConfig)
class FeedbackRetryRouter(FlockRouter):
    """Routes based on assertion feedback in the context.

    If feedback exists for the current agent and retries are not exhausted,
    it routes back to the same agent, adding the feedback to its input.
    Otherwise, it can route to a fallback agent or stop the chain.
    """

    name: str = "feedback_retry_router"
    config: FeedbackRetryRouterConfig = Field(
        default_factory=FeedbackRetryRouterConfig
    )

    async def route(
        self,
        current_agent: FlockAgent,
        result: dict[str, Any],
        context: FlockContext,
    ) -> HandOffRequest:
        feedback = context.get_variable(self.config.feedback_context_key)

        if feedback:
            logger.warning(
                f"Assertion feedback detected for agent '{current_agent.name}'. Attempting retry."
            )

            retry_key = f"{self.config.retry_count_context_key_prefix}{current_agent.name}"
            retry_count = context.get_variable(retry_key, 0)
            logger.warning(f"Feedback: {feedback} - Retry Count {retry_count}")

            if retry_count < self.config.max_retries:
                logger.info(
                    f"Routing back to agent '{current_agent.name}' for retry #{retry_count + 1}"
                )
                context.set_variable(retry_key, retry_count + 1)
                context.set_variable(
                    f"{current_agent.name}_prev_result", result
                )
                # Add feedback to the *next* agent's input (which is the same agent)
                # Requires the agent's signature to potentially accept a 'feedback' input field.
                return HandOffRequest(
                    next_agent=current_agent.name,
                    output_to_input_merge_strategy="match",  # Add feedback to existing context/previous results
                    add_input_fields=[
                        f"{self.config.feedback_context_key} | Feedback for prev result",
                        f"{current_agent.name}_prev_result | Previous Result",
                    ],
                    add_description=f"Try to fix the previous result based on the feedback.",
                    override_context=None,  # Context already updated with feedback and retry count
                )
            else:
                logger.error(
                    f"Max retries ({self.config.max_retries}) exceeded for agent '{current_agent.name}'."
                )
                # Max retries exceeded, route to fallback or stop
                if self.config.fallback_agent:
                    logger.info(
                        f"Routing to fallback agent '{self.config.fallback_agent}'"
                    )
                    # Clear feedback before going to fallback? Optional.
                    if self.config.feedback_context_key in context.state:
                        del context.state[self.config.feedback_context_key]
                    return HandOffRequest(next_agent=self.config.fallback_agent)
                else:
                    logger.info("No fallback agent defined. Stopping workflow.")
                    return HandOffRequest(next_agent="")  # Stop the chain

        else:
            # No feedback, assertions passed or module not configured for feedback
            logger.debug(
                f"No assertion feedback for agent '{current_agent.name}'. Proceeding normally."
            )
            # Default behavior: Stop the chain if no other routing is defined
            # In a real system, you might chain this with another router (e.g., LLMRouter)
            # to decide the *next different* agent if assertions passed.
            return HandOffRequest(next_agent="")  # Stop or pass to next router
