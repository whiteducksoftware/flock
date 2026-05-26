---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# ⛓️ Chaining Agents: Building Workflows with Routers

In Flock, individual agents are powerful, but the real magic happens when you connect them to form sophisticated workflows. Chaining allows the output of one agent to become the input for another, enabling complex tasks to be broken down into manageable, specialized steps.

The key to chaining lies in **Routers**. Every `FlockAgent` can have a `handoff_router` attached. After an agent successfully completes its `evaluate` step, its router is called to decide what happens next.

## How Routers Work: The `HandOffRequest`

A `FlockRouter`'s primary job is to execute its `route` method. This method receives:

1.  `current_agent`: The agent instance that just finished.
2.  `result`: The dictionary output produced by the `current_agent`.
3.  `context`: The shared `FlockContext` object containing the overall workflow state and history.

Based on these inputs, the router returns a `HandOffRequest` object. This object tells the Flock workflow engine:

*   `next_agent` (str): The `name` of the agent to execute next. If empty or `None`, the workflow typically terminates.
*   `output_to_input_merge_strategy` (Literal["match", "add"]): How the `result` from the current agent should be incorporated into the context for the next agent.
    *   `"match"` (Default): Fields in the `result` update corresponding fields in the context.
    *   `"add"`: The entire `result` dictionary is added to the context, often under a specific key (useful for feedback or passing complex objects).
*   Optional Overrides: The `HandOffRequest` can also potentially carry information to override aspects of the next agent's execution or update the context directly (though specific router implementations vary in how they use this).

Flock provides several built-in router types to handle different chaining scenarios:

## 1. Static Chaining: `DefaultRouter`

The simplest way to chain agents. The `DefaultRouter` routes to a predetermined next agent specified in its configuration.

```python
# --- In your agent definition ---
from flock.core import FlockFactory
from flock.routers.default import DefaultRouter, DefaultRouterConfig

# Agent A always hands off to Agent B
agent_a = FlockFactory.create_default_agent(
    name="agent_a",
    input="topic",
    output="summary",
    router=DefaultRouter(
        config=DefaultRouterConfig(hand_off="agent_b") # Always go to agent_b
    )
)

agent_b = FlockFactory.create_default_agent(
    name="agent_b",
    input="summary", # Expects output from agent_a
    output="final_report"
)

flock.add_agent(agent_a)
flock.add_agent(agent_b)

# Run starting with agent_a
flock.run(start_agent=agent_a, input={"topic": "AI Agents"})
```

The `hand_off` value in `DefaultRouterConfig` can also be a callable function that dynamically returns a `HandOffRequest` based on the context or result.

## 2. Dynamic Chaining: Making Decisions

For more complex workflows, you need routers that can make decisions based on the current state.

### LLM-Powered Routing: `LLMRouter` 🧠

This router leverages a Large Language Model (LLM) to decide the next best agent.

*   **How it works:** It constructs a prompt containing the current agent's details, its output, and information about all other available agents (their names, descriptions, inputs/outputs). It asks the LLM to choose the most suitable next agent, provide a confidence score, and explain its reasoning.
*   **Configuration:** You can set the LLM `model`, `temperature`, `max_tokens`, a `confidence_threshold` (to only proceed if the LLM is confident enough), and even provide a custom prompt template.
*   **Use Case:** Ideal for workflows where the next step depends on nuanced understanding of the previous agent's output and the capabilities of potential next agents.

```python
# --- Conceptual Example ---
from flock.routers.llm import LLMRouter, LLMRouterConfig

smart_router = LLMRouter(
    config=LLMRouterConfig(
        confidence_threshold=0.7, # Only route if LLM score is >= 0.7
        temperature=0.1
    )
)

agent_with_llm_routing = FlockFactory.create_default_agent(
    name="decision_point_agent",
    # ... inputs/outputs ...
    router=smart_router
)
```

### Agent-Powered Routing: `AgentRouter` 🤖

This router delegates the routing decision to *another* specialized `FlockAgent` called the `HandoffAgent`.

*   **How it works:** The `AgentRouter` gathers information about the current agent, its result, and the available next agents. It packages this information and feeds it to the internal `HandoffAgent`. The `HandoffAgent` (which typically uses a `DeclarativeEvaluator`) analyzes the situation and outputs its decision (next agent name, confidence, reasoning). The `AgentRouter` then uses this decision.
*   **Configuration:** Includes a `confidence_threshold`.
*   **Use Case:** Useful when the routing logic itself is complex enough to warrant its own dedicated agent. It allows the routing logic to be developed and potentially improved independently.

```python
# --- Conceptual Example ---
from flock.routers.agent import AgentRouter, AgentRouterConfig

agent_powered_router = AgentRouter(
    config=AgentRouterConfig(
        confidence_threshold=0.6
    )
)

agent_with_agent_routing = FlockFactory.create_default_agent(
    name="complex_routing_agent",
    # ... inputs/outputs ...
    router=agent_powered_router
)
```

## 3. Conditional Routing & Retries

Sometimes, the workflow needs to branch or repeat based on specific conditions or feedback.

### Condition-Based Branching: `ConditionalRouter` 🤔

This router evaluates a condition based on a value stored in the `FlockContext` and routes accordingly.

*   **How it works:** You configure it to check a specific `condition_context_key`. It supports various checks:
    *   String comparison (equals, contains, regex, etc.)
    *   Number comparison (<, ==, >, etc.)
    *   List size checks (min/max items)
    *   Type checking (`isinstance`)
    *   Boolean checks
    *   Existence checks (does the key exist?)
    *   Custom logic via a registered callable function.
*   **Routing Paths:** It routes to `success_agent` if the condition passes, or `failure_agent` if it fails.
*   **Retry Logic:** Optionally, if the condition fails, it can route back to a `retry_agent` (often the *same* agent) up to `max_retries` times before finally giving up and going to the `failure_agent`. This is useful for self-correction loops.
*   **Use Case:** Implementing if/else logic, validation checks, or simple retry loops within your workflow.

```python
# --- Conceptual Example ---
from flock.routers.conditional import ConditionalRouter, ConditionalRouterConfig

# Assume an agent 'validator_agent' puts its result in context.state['validation_status']
conditional_router = ConditionalRouter(
    config=ConditionalRouterConfig(
        condition_context_key="validation_status", # Check this context variable
        expected_string="PASS", # Condition: Does it equal "PASS"?
        string_mode="equals",
        ignore_case=True,
        success_agent="publish_agent", # If "PASS", go to publish
        failure_agent="human_review_agent" # If not "PASS", go to review
    )
)

validator_agent = FlockFactory.create_default_agent(
    name="validator_agent",
    # ... inputs/outputs ...
    # Assume it sets context.state['validation_status'] = "PASS" or "FAIL"
    router=conditional_router
)
```

### Feedback-Driven Retries: `FeedbackRetryRouter` 🔁

This router is specifically designed to handle retries based on feedback, often generated by assertion modules.

*   **How it works:** It checks a configured `feedback_context_key`. If feedback is present (indicating a failure or issue detected, perhaps by an `AssertionCheckerModule`), and `max_retries` hasn't been exceeded, it routes back to the *current agent*. Crucially, it uses `output_to_input_merge_strategy="add"` and `add_input_fields` to inject the feedback message (and potentially the previous result) into the context, making it available for the agent's next attempt. If retries are exhausted, it routes to a `fallback_agent` or stops.
*   **Use Case:** Implementing self-correction loops where an agent attempts a task, an assertion module checks the result, and if issues are found, the agent retries with specific feedback on what went wrong.

```python
# --- Conceptual Example ---
from flock.routers.feedback import FeedbackRetryRouter, FeedbackRetryRouterConfig
# Assume AssertionCheckerModule puts feedback in context.state['flock.assertion_feedback']

retry_router = FeedbackRetryRouter(
    config=FeedbackRetryRouterConfig(
        max_retries=2, # Allow 2 retries
        feedback_context_key="flock.assertion_feedback", # Check this key
        fallback_agent="error_handler_agent" # Go here if retries fail
    )
)

# Agent that might fail assertions
correctable_agent = FlockFactory.create_default_agent(
    name="correctable_agent",
    input="task_description, flock.assertion_feedback | Optional feedback", # Agent needs to accept feedback
    output="result_data",
    # Assume AssertionCheckerModule runs after evaluate
    router=retry_router
)
```

## 4. Iterative Generation: `IterativeListGeneratorRouter` 🔄

This router facilitates scenarios where an agent needs to be called repeatedly to build up a list of items.

*   **How it works:** It routes back to the *same agent* multiple times. It manages the growing list of generated items and the current iteration count within the `FlockContext`. On each subsequent run, it provides the list of previously generated items back to the agent (via a configured `context_input_field`). It stops once `max_iterations` is reached.
*   **Complexity:** This pattern can be complex because the agent ideally needs slightly different inputs (the growing list) and might only need to produce *one* new item per iteration, rather than the full final list. The router attempts to manage this state, but careful agent and signature design is required.
*   **Use Case:** Generating list items one by one, like chapters for a book outline, steps in a plan, or ideas in a brainstorm, where each new item might depend on the previous ones.

```python
# --- Conceptual Example ---
from flock.routers.list_generator import IterativeListGeneratorRouter, IterativeListGeneratorRouterConfig

list_router = IterativeListGeneratorRouter(
    config=IterativeListGeneratorRouterConfig(
        target_list_field="chapters", # The final list output name
        item_output_field="chapter", # The output field for a single item
        context_input_field="previous_chapters", # How the list is passed back
        max_iterations=5 # Generate up to 5 chapters
    )
)

chapter_agent = FlockFactory.create_default_agent(
    name="chapter_agent",
    input="book_topic, previous_chapters | List of previously generated chapters",
    output="chapter | The next chapter details", # Agent generates one item
    router=list_router
)
# Note: The final result containing the full 'chapters' list is typically
# assembled from the context after the iterations complete.
```

## Combining Routers

For truly advanced workflows, you might even chain routers themselves (though this requires careful design). For example, a `FeedbackRetryRouter` could handle immediate retries, and if no feedback is present (success), it could hand off to an `LLMRouter` to decide the *next different* agent.

Just create a new router which is calling both routers in sequence! And even more wild shenanigans are possible!

---

By understanding and utilizing these different router types, you can move beyond simple linear sequences and build dynamic, intelligent, and robust agent workflows with Flock! 🚀
