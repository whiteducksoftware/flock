"""FlockAgent is the core, declarative base class for all agents in the Flock framework."""

import asyncio
import json
import os
import uuid
from abc import ABC
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, Literal, TypeVar, Union

import cloudpickle
import numpy as np
from pydantic import BaseModel, Field
from tqdm import tqdm

from flock.core.context.context import FlockContext
from flock.core.logging.formatters.themed_formatter import (
    ThemedAgentResultFormatter,
)
from flock.core.logging.formatters.themes import OutputTheme
from flock.core.logging.logging import get_logger
from flock.core.memory.memory_parser import MemoryMappingParser
from flock.core.memory.memory_storage import (
    FilterOperation,
    FlockMemoryStore,
    MemoryEntry,
    SemanticOperation,
)
from flock.core.mixin.dspy_integration import AgentType, DSPyIntegrationMixin
from flock.core.mixin.prompt_parser import PromptParserMixin

logger = get_logger("agent")


from opentelemetry import trace

tracer = trace.get_tracer(__name__)


T = TypeVar("T", bound="FlockAgent")


class FlockAgentConfig(BaseModel):
    """Configuration options for a FlockAgent."""

    agent_type_override: AgentType = Field(
        default=None,
        descriptions={
            "description": "Overrides the agent type. TOOL USE ONLY WORKS WITH REACT"
        },
    )
    disable_output: bool = Field(
        default=False,
        descriptions="Disables the agent's output.",
    )
    temperature: float = Field(
        default=0.0, descriptions="Temperature for the LLM"
    )
    max_tokens: int = Field(default=2000, descriptions="Max tokens for the LLM")


class FlockAgentMemoryConfig(BaseModel):
    """Flock Agent Memory Configuration."""

    storage_type: Literal["json", "in_memory"] = Field(
        default="json", descriptions="Storage type for memory"
    )
    file_path: str = Field(
        default="agent_memory.json", descriptions="File path for memory storage"
    )
    save_memory_after_every_update: bool = Field(
        default=True,
        descriptions="Saves the memory after every update",
    )
    similarity_threshold: float = Field(
        default=0.5, descriptions="Similarity threshold for memory"
    )
    context_window: int = Field(
        default=3, descriptions="Number of memory entries to return"
    )
    max_length: int = Field(
        default=1000, descriptions="Max length of memory entry before splitting"
    )


class FlockAgentOutputConfig(BaseModel):
    """Configuration options for a FlockAgent."""

    render_table: bool = Field(default=False, descriptions="Renders a table.")
    theme: OutputTheme = Field(  # type: ignore
        default=OutputTheme.afterglow,
        descriptions="Disables the agent's output.",
    )
    max_length: int = Field(
        default=1000,
        descriptions="Disables the agent's output.",
    )
    wait_for_input: bool = Field(default=False, descriptions="Wait for input.")
    write_to_file: bool = Field(default=False, descriptions="Write to file.")


class HandOff(BaseModel):
    """Base class for handoff returns."""

    next_agent: Union[str, "FlockAgent"] = Field(
        default="", description="Next agent to invoke"
    )
    input: dict[str, Any] = Field(
        default_factory=dict,
        description="Input data for the next agent",
    )
    context: FlockContext = Field(
        default=None, descrio="Override context parameters"
    )


class FlockAgent(BaseModel, ABC, PromptParserMixin, DSPyIntegrationMixin):
    """FlockAgent is the core, declarative base class for all agents in the Flock framework.

    Due to its declarative nature, FlockAgent does not rely on constructing classical prompts manually.
    Instead, each agent is defined by simply declaring:
    - Its expected inputs (what data it needs),
    - Its expected outputs (what data it produces), and
    - Any optional tools it can use during execution.

    In a declarative model, you describe *what* you expect rather than *how* to compute it. This means that
    instead of embedding prompt engineering logic directly in your code, you specify a concise signature.
    At runtime, the Flock framework automatically:
    - Resolves the inputs from a pre-computed context,
    - Constructs a precise prompt for the underlying language model (using metadata such as type hints
        and human-readable descriptions), and
    - Invokes the appropriate tools if needed.

    This approach minimizes hidden dependencies and boilerplate code. It allows developers to focus solely on
    what data the agent should work with and what result it should produce, without worrying about the intricacies
    of prompt formatting or context management.

    For details on how Flock resolves inputs, please refer to the documentation.

    Key benefits of the declarative approach include:
    - **Clarity:** The agent's interface (inputs and outputs) is explicitly defined.
    - **Reusability:** Agents can be easily serialized, shared, and reused since they are built as Pydantic models.
    - **Modularity:** By receiving a dictionary of pre-resolved inputs, agents operate independently of the global context,
        making them easier to test and debug.
    - **Extensibility:** Additional metadata (like detailed descriptions for each key) can be embedded and later used to
        refine the prompt for the LLM.

    Since FlockAgent is a Pydantic BaseModel, it can be serialized to and from JSON. This ensures that the agent's
    configuration and state are easily stored, transmitted, and reproduced.

    **Implementation Example:**

    Below is an example of how to define and instantiate a FlockAgent:

        from flock_agent import FlockAgent
        import basic_tools

        # Define an agent by declaring its inputs, outputs, and optional tools.
        idea_agent = FlockAgent(
            name="idea_agent",
            input="query: str | The search query, context: dict | The full conversation context",
            output="a_fun_software_project_idea: str | The generated software project idea",
            tools=[basic_tools.web_search_tavily],
        )

        # At runtime, Flock automatically resolves inputs and calls the agent:
        resolved_inputs = {
            "query": "A new social media app",
            "context": {"previous_idea": "a messaging platform"}
        }
        result = await idea_agent.run(resolved_inputs)

    In this example:
    - The agent declares that it needs a `query` (a string describing what to search for) and a `context` (a dictionary
        containing additional information).
    - It produces a `a_fun_software_project_idea` (a string with the generated idea).
    - The tool `basic_tools.web_search_tavily` is available for the agent to use if needed.
    - When the agent is run, the Flock framework resolves the inputs, constructs the appropriate prompt using the
        declared metadata, and returns the result.

    This declarative style streamlines agent creation and execution, making the framework highly modular, testable,
    and production-ready.

    In the future options will be provided to optimize the "hidden" prompt generation and execution so the agent will
    perform close to its theoretical maximum.
    """

    name: str = Field(..., description="Unique identifier for the agent.")
    model: str | None = Field(
        None, description="The model to use (e.g., 'openai/gpt-4o')."
    )
    description: str | Callable[..., str] = Field(
        "", description="A human-readable description of the agent."
    )

    input: str | Callable[..., str] | None = Field(
        None,
        description=(
            "A comma-separated list of input keys. Optionally supports type hints (:) and descriptions (|). "
            "For example: 'query: str | The search query, chapter_list: list[str] | The chapter list of the document'."
        ),
    )
    output: str | Callable[..., str] | None = Field(
        None,
        description=(
            "A comma-separated list of output keys.  Optionally supports type hints (:) and descriptions (|). "
            "For example: 'result|The generated result, summary|A brief summary'."
        ),
    )

    tools: list[Callable[..., Any] | Any] | None = Field(
        default=None,
        description="An optional list of callable tools that the agent can leverage during execution.",
    )

    use_cache: bool = Field(
        default=True,
        description="Set to True to enable caching of the agent's results.",
    )

    hand_off: str | Callable[..., Any] | None = Field(
        None,
        description=(
            "Specifies the next agent in the workflow or a callable that determines the handoff. "
            "This allows chaining of agents."
        ),
    )

    termination: str | Callable[..., str] | None = Field(
        None,
        description="An optional termination condition or phrase used to indicate when the agent should stop processing.",
    )

    config: FlockAgentConfig = Field(
        default_factory=FlockAgentConfig,
        description="Configuration options for the agent, such as serialization settings.",
    )

    output_config: FlockAgentOutputConfig = Field(
        default_factory=FlockAgentOutputConfig,
        description="Configuration options for the agent's output.",
    )

    memory_config: FlockAgentMemoryConfig = Field(
        default_factory=FlockAgentMemoryConfig,
        description="Configuration options for the agent's memory.",
    )

    memory_enabled: bool = Field(
        default=False,
        description="Enable memory for this agent",
    )
    memory_mapping: str | None = Field(default=None)
    memory_store: FlockMemoryStore | None = Field(default=None)
    memory_ops: list | None = Field(default=None)

    # Lifecycle callback fields: if provided, these callbacks are used instead of overriding the methods.
    initialize_callback: Callable[[dict[str, Any]], Awaitable[None]] | None = (
        Field(
            default=None,
            description="Optional callback function for initialization. If provided, this async function is called with the inputs.",
        )
    )
    evaluate_callback: (
        Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None
    ) = Field(
        default=None,
        description="Optional callback function for evaluate. If provided, this async function is called with the inputs instead of the internal evaluate",
    )
    terminate_callback: (
        Callable[[dict[str, Any], dict[str, Any]], Awaitable[None]] | None
    ) = Field(
        default=None,
        description="Optional callback function for termination. If provided, this async function is called with the inputs and result.",
    )
    on_error_callback: (
        Callable[[Exception, dict[str, Any]], Awaitable[None]] | None
    ) = Field(
        default=None,
        description="Optional callback function for error handling. If provided, this async function is called with the error and inputs.",
    )

    # Lifecycle hooks
    async def initialize(self, inputs: dict[str, Any]) -> None:
        """Called at the very start of the agent's execution.

        Override this method or provide an `initialize_callback` to perform setup tasks such as input validation or resource loading.
        """
        if self.memory_enabled and self.memory_store is None:
            file_path = None
            if self.memory_config:
                file_path = self.memory_config.file_path
            else:
                self.memory_config = FlockAgentMemoryConfig()
            self.memory_store = FlockMemoryStore.load_from_file(file_path)

        if self.memory_mapping is None:
            self.memory_ops = []
            self.memory_ops.append(SemanticOperation())
        else:
            self.memory_ops = MemoryMappingParser().parse(self.memory_mapping)

        if self.initialize_callback is not None:
            await self.initialize_callback(self, inputs)
        else:
            pass

    async def terminate(
        self, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Called at the very end of the agent's execution.

        Override this method or provide a `terminate_callback` to perform cleanup tasks such as releasing resources or logging results.
        """
        if self.terminate_callback is not None:
            await self.terminate_callback(self, inputs, result)
        else:
            pass

    async def on_error(self, error: Exception, inputs: dict[str, Any]) -> None:
        """Called if the agent encounters an error during execution.

        Override this method or provide an `on_error_callback` to implement custom error handling or recovery strategies.
        """
        if self.on_error_callback is not None:
            await self.on_error_callback(self, error, inputs)
        else:
            pass

    async def evaluate(
        self, inputs: dict[str, Any], memory_result=None
    ) -> dict[str, Any]:
        """Process the agent's task using the provided inputs and return the result.

        This asynchronous method is the core execution engine for a FlockAgent. It performs the following steps:

        1. **Extract Descriptions:**
            Parses the agent's configured input and output strings to extract human-readable descriptions.
            These strings are expected to use the format "key: type_hint | description". The method removes the
            type hints and builds dictionaries that map each key to its corresponding description.

        2. **Construct the Prompt:**
            Based on the extracted descriptions, the method builds a detailed prompt that clearly lists all input
            fields (with their descriptions) and output fields. This prompt is designed to guide the language model,
            ensuring that it understands what inputs are provided and what outputs are expected.

        3. **Configure the Language Model:**
            The method initializes and configures a language model using the dspy library. The agent's model
            (e.g., "openai/gpt-4o") is used to set up the language model, ensuring that it is ready to process the prompt.

        4. **Execute the Task:**
            Depending on whether the agent has been configured with additional tools:
                - **With Tools:** A ReAct task is instantiated. This task interleaves reasoning and tool usage,
                allowing the agent to leverage external functionalities during execution.
                - **Without Tools:** A Predict task is used for a straightforward generation based on the prompt.

        5. **Process the Result:**
            After execution, the method attempts to convert the result to a dictionary. It also ensures that each
            expected input key is present in the output (by setting a default value from the inputs if necessary).

        6. **Error Handling:**
            Any exceptions raised during the process are caught, logged (or printed), and then re-raised to allow
            higher-level error handling. This ensures that errors are not silently ignored and can be properly diagnosed.

        **Arguments:**
            inputs (dict[str, Any]): A dictionary containing all the resolved input values required by the agent.
                These inputs are typically obtained from the global context or from the output of a previous agent.

        **Returns:**
            dict[str, Any]: A dictionary containing the output generated by the agent. This output adheres to the
                agent's declared output fields and includes any fallback values for missing inputs.

        **Usage Example:**

            Suppose an agent is declared with the following configuration:
                input = "query: str | The search query, context: dict | Additional context"
                output = "idea: str | The generated software project idea"

            When invoked with:
                inputs = {"query": "build an app", "context": {"previous_idea": "messaging app"}}

            The method will:
                - Parse the descriptions to create:
                    input_descriptions = {"query": "The search query", "context": "Additional context"}
                    output_descriptions = {"idea": "The generated software project idea"}
                - Construct a prompt that lists these inputs and outputs clearly.
                - Configure the language model and execute the appropriate task (ReAct if tools are provided, otherwise Predict).
                - Return a dictionary similar to:
                    {"idea": "A fun app idea based on ...", "query": "build an app", "context": {"previous_idea": "messaging app"}}
        """
        with tracer.start_as_current_span("agent.evaluate") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            if self.evaluate_callback is not None:
                return await self.evaluate_callback(self, inputs)
            try:
                input_definition = self.input
                if memory_result:
                    input_definition = (
                        input_definition
                        + ", memory_result: dict | The result from memory"
                    )
                    inputs["memory_result"] = memory_result
                # Create and configure the signature and language model.
                self.__dspy_signature = self.create_dspy_signature_class(
                    self.name,
                    self.description,
                    f"{input_definition} -> {self.output}",
                )
                self._configure_language_model()
                agent_task = self._select_task(
                    self.__dspy_signature,
                    agent_type_override=self.config.agent_type_override,
                )
                # Execute the task.
                result = agent_task(**inputs)
                result = self._process_result(result, inputs)
                span.set_attribute("result", str(result))
                logger.info("Evaluation successful", agent=self.name)
                return result
            except Exception as eval_error:
                logger.error(
                    "Error during evaluation",
                    agent=self.name,
                    error=str(eval_error),
                )
                span.record_exception(eval_error)
                raise

    def save_to_file(self, file_path: str | None = None) -> None:
        """Save the serialized agent to a file."""
        if file_path is None:
            file_path = f"{self.name}.json"
        dict_data = self.to_dict()

        # create all needed directories
        path = os.path.dirname(file_path)
        if path:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w") as file:
            file.write(json.dumps(dict_data))

    async def _extract_concepts(self, text: str) -> set[str]:
        """Extract concepts using DSPy integration."""
        existing_concepts = None
        if self.memory_store.concept_graph:
            existing_concepts = set(
                self.memory_store.concept_graph.graph.nodes()
            )

        input_def = "text: str | Text to analyze"
        if existing_concepts:
            input_def += ", existing_concepts: list[str] | Already known concepts that might apply"

        # Create a signature for concept extraction
        concept_signature = self.create_dspy_signature_class(
            f"{self.name}_concept_extractor",
            "Extract key concepts from text",
            f"{input_def} -> concepts: list[str] | Max five key concepts all lower case",
        )

        # Configure and run the predictor
        self._configure_language_model()
        predictor = self._select_task(concept_signature, "Completion")
        result = predictor(text=text, existing_concepts=list(existing_concepts))

        # Convert to set
        concept_list = result.concepts if hasattr(result, "concepts") else []
        concepts = set(concept_list)
        logger.debug(f"Extracted concepts: {concept_list}")
        return concepts

    async def evaluate_memory(
        self, inputs: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Check memory before main evaluation."""
        if not self.memory_enabled or not self.memory_store:
            return None

        try:
            # Convert input to embedding
            input_text = json.dumps(inputs)
            query_embedding = self.memory_store.compute_embedding(input_text)

            # Extract concepts from input
            concepts = await self._extract_concepts(input_text)

            memory_results = []
            for op in self.memory_ops:
                if op.type == "semantic":
                    # Semantic search
                    semantic_results = self.memory_store.retrieve(
                        query_embedding,
                        concepts,
                        similarity_threshold=op.threshold,
                    )
                    memory_results.extend(semantic_results)

                elif op.type == "exact":
                    # Exact matching
                    exact_results = self.memory_store.exact_match(inputs)
                    memory_results.extend(exact_results)

                elif op.type == "filter":
                    # Apply filters
                    memory_results = [
                        entry
                        for entry in memory_results
                        if self._apply_filters(entry, op)
                    ]

                elif op.type == "combine":
                    # Combine results using weights
                    memory_results = self.memory_store.combine_results(
                        inputs, op.weights
                    ).get("combined_results", [])

            if memory_results:
                logger.debug(
                    f"Found {len(memory_results)} relevant memories after operations",
                    agent=self.name,
                )
                return {"memory_results": memory_results}

            return None

        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e!s}", agent=self.name)
            return None

    def _apply_filters(
        self, entry: MemoryEntry, filter_op: FilterOperation
    ) -> bool:
        """Apply filter operation to memory entry."""
        # Check recency if specified
        if filter_op.recency:
            cutoff = self._parse_time_window(filter_op.recency)
            if entry.timestamp < cutoff:
                return False

        # Check relevance if specified
        if filter_op.relevance is not None:
            relevance_score = entry.decay_factor * np.log1p(entry.access_count)
            if relevance_score < filter_op.relevance:
                return False

        # Check metadata if specified
        if filter_op.metadata:
            entry_metadata = getattr(entry, "metadata", {})
            for key, value in filter_op.metadata.items():
                if key not in entry_metadata or entry_metadata[key] != value:
                    return False

        return True

    def _parse_time_window(self, window: str) -> datetime:
        """Parse time window string (e.g., '7d', '24h') into datetime."""
        value = int(window[:-1])
        unit = window[-1]

        if unit == "d":
            delta = timedelta(days=value)
        elif unit == "h":
            delta = timedelta(hours=value)
        else:
            raise ValueError(f"Unknown time unit: {unit}")

        return datetime.now() - delta

    def save_memory_graph(self, file_path: str) -> None:
        """Save the memory graph to a file."""
        if self.memory_store:
            json_str = self.memory_store.model_dump_json()
            with open(file_path, "w") as file:
                file.write(json_str)

    def export_memory_graph(self, file_path: str) -> None:
        """Export the memory graph to an image file."""
        if self.memory_store:
            self.memory_store.concept_graph.save_as_image(file_path)

    async def _split_entry(
        self, inputs: dict[str, Any], result: dict[str, Any]
    ) -> list[dict]:
        """Split entries using DSPy for intelligent chunking."""
        # Create splitter signature
        split_signature = self.create_dspy_signature_class(
            f"{self.name}_splitter",
            "Split content into meaningful, self-contained chunks",
            """
            content: str | The content to split
            -> chunks: list[dict[str,str]] | List of chunks with content as key and summary as value
            """,
        )

        # Configure and run the predictor
        self._configure_language_model()
        splitter = self._select_task(split_signature, "Completion")

        # Get the content to split
        full_text = json.dumps(inputs) + json.dumps(result)
        split_result = splitter(content=full_text)

        chunks = []
        for i, chunk in tqdm(enumerate(split_result.chunks)):
            # Create memory entry for each chunk
            chunk_entry = {
                "inputs": {
                    "original_inputs": inputs,
                    "chunk_index": i,
                    "total_chunks": len(split_result.chunks),
                    "chunk_summary": chunk["summary"],
                },
                "outputs": {
                    "chunk_content": chunk["content"],
                    "original_result": result,
                },
            }
            chunks.append(chunk_entry)

            # Extract concepts for each chunk separately
            chunk_concepts = await self._extract_concepts(chunk["content"])
            logger.debug(f"Chunk {i} concepts: {list(chunk_concepts)}")

            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                inputs=chunk_entry["inputs"],
                outputs=chunk_entry["outputs"],
                embedding=self.memory_store.compute_embedding(
                    chunk["content"]
                ).tolist(),
                concepts=chunk_concepts,
                timestamp=datetime.now(),
            )

            # Add to memory store
            self.memory_store.add_entry(entry)
            logger.debug(
                "Stored interaction in memory",
                agent=self.name,
                entry_id=entry.id,
                concepts=chunk_concepts,
            )

        return chunks

    async def _store_single_entry(
        self, full_text: str, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        concepts = await self._extract_concepts(full_text)
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            inputs=inputs,
            outputs=result,
            embedding=self.memory_store.compute_embedding(full_text).tolist(),
            concepts=concepts,
            timestamp=datetime.now(),
        )

        # Add to memory store
        self.memory_store.add_entry(entry)
        logger.debug(
            "Stored interaction in memory",
            agent=self.name,
            entry_id=entry.id,
            concepts=concepts,
        )

    async def update_memory(
        self, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Store results in memory after evaluation."""
        if not self.memory_enabled or not self.memory_store:
            return
        try:
            full_text = json.dumps(inputs) + json.dumps(result)
            if (
                len(full_text) > self.memory_config.max_length
            ):  # configurable threshold
                # Split and store chunks
                await self._split_entry(inputs, result)
            else:
                # Store as single entry
                await self._store_single_entry(full_text, inputs, result)
        except Exception as e:
            logger.warning(f"Memory storage failed: {e!s}", agent=self.name)

    @classmethod
    def load_from_file(cls: type[T], file_path: str) -> T:
        """Load a serialized agent from a file."""
        with open(file_path) as file:
            data = json.load(file)
        # Fallback: use the current class.
        return cls.from_dict(data)

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given inputs and return its generated output."""
        return asyncio.run(self.run_async(inputs))

    async def run_async(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given inputs and return its generated output.

        This method represents the primary execution flow for a FlockAgent and performs the following
        lifecycle steps in sequence:

        1. **Initialization:**
            Calls the `initialize(inputs)` hook to perform any necessary pre-run setup, such as input
            validation, resource allocation, or logging. This ensures that the agent is properly configured
            before processing begins.

        2. **Evaluation:**
            Invokes the internal `_evaluate(inputs)` method, which constructs a detailed prompt (incorporating
            input and output descriptions), configures the underlying language model via dspy, and executes the
            main task (using a ReAct task if tools are provided, or a Predict task otherwise).

        3. **Termination:**
            Calls the `terminate(inputs, result)` hook after evaluation, allowing the agent to clean up any
            resources or perform post-run actions (such as logging the output).

        4. **Output Return:**
            Returns a dictionary containing the agent's output. This output conforms to the agent's declared
            output fields and may include any default or fallback values for missing inputs.

        If an error occurs during any of these steps, the `on_error(error, inputs)` hook is invoked to handle
        the exception (for instance, by logging detailed error information). The error is then re-raised, ensuring
        that higher-level error management can address the failure.

        **Arguments:**
            inputs (dict[str, Any]): A dictionary containing the resolved input values required by the agent.
                These inputs are typically derived from the agent's declared input signature and may include data
                provided by previous agents or from a global context.

        **Returns:**
            dict[str, Any]: A dictionary containing the output generated by the agent. The output structure
            adheres to the agent's declared output fields.

        **Example:**
            Suppose an agent is defined with:
                input  = "query: str | The search query, context: dict | Additional context"
                output = "result: str | The generated idea"
            When executed with:
                inputs = {"query": "build a chatbot", "context": {"user": "Alice"}}
            The method might return:
                {"result": "A conversational chatbot that uses AI to...", "query": "build a chatbot", "context": {"user": "Alice"}}
        """
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            try:
                await self.initialize(inputs)
                memory_result = await self.evaluate_memory(inputs)
                result = await self.evaluate(
                    inputs, memory_result=memory_result
                )
                self.display_output(result)
                await self.update_memory(inputs, result)
                await self.terminate(inputs, result)
                span.set_attribute("result", str(result))
                logger.info("Agent run completed", agent=self.name)
                return result
            except Exception as run_error:
                logger.error(
                    "Error running agent", agent=self.name, error=str(run_error)
                )
                await self.on_error(run_error, inputs)
                span.record_exception(run_error)
                raise

    def display_info(self) -> None:
        pass

    def display_output(self, result: dict[str, Any]) -> None:
        """Display the agent's output using the configured output formatter."""
        ThemedAgentResultFormatter(
            self.output_config.theme,
            self.output_config.max_length,
            self.output_config.render_table,
            self.output_config.wait_for_input,
            self.output_config.write_to_file,
        ).display_result(result, self.name)

    async def run_temporal(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute this agent via a Temporal workflow for enhanced fault tolerance and asynchronous processing.

        This method enables remote execution of the agent within a Temporal environment, leveraging Temporal's
        capabilities for persistence, retries, and distributed error handling. The workflow encapsulates the agent's
        logic so that it can run on Temporal workers, providing robustness and scalability in production systems.

        The method performs these steps:
        1. **Connect to Temporal:**
            Establishes a connection to the Temporal server using a Temporal client configured with the appropriate
            namespace (default is "default").
        2. **Serialization:**
            Serializes the agent instance (via `to_dict()`) along with the provided inputs. This step converts any
            callable objects (e.g., lifecycle hooks or tools) into a storable format using cloudpickle.
        3. **Activity Invocation:**
            Triggers a designated Temporal activity (e.g., `run_flock_agent_activity`) by passing the serialized agent
            data and inputs. The Temporal activity is responsible for executing the agent's logic in a fault-tolerant
            manner.
        4. **Return Output:**
            Awaits and returns the resulting output from the Temporal workflow as a dictionary, consistent with the
            output structure of the local `run()` method.

        If any error occurs during these steps, the error is logged and re-raised to ensure that failure is properly
        handled by higher-level error management systems.

        **Arguments:**
            inputs (dict[str, Any]): A dictionary containing the resolved inputs required by the agent, similar to those
                provided to the local `run()` method.

        **Returns:**
            dict[str, Any]: A dictionary containing the output produced by the agent after remote execution via Temporal.
                The output format is consistent with that of the local `run()` method.

        **Example:**
            Given an agent defined with:
                input  = "query: str | The search query, context: dict | Additional context"
                output = "result: str | The generated idea"
            Calling:
                result = await agent.run_temporal({"query": "analyze data", "context": {"source": "sales"}})
            will execute the agent on a Temporal worker and return the output in a structured dictionary format.
        """
        with tracer.start_as_current_span("agent.run_temporal") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            try:
                from temporalio.client import Client

                from flock.workflow.agent_activities import (
                    run_flock_agent_activity,
                )
                from flock.workflow.temporal_setup import run_activity

                client = await Client.connect(
                    "localhost:7233", namespace="default"
                )
                agent_data = self.to_dict()
                inputs_data = inputs

                result = await run_activity(
                    client,
                    self.name,
                    run_flock_agent_activity,
                    {"agent_data": agent_data, "inputs": inputs_data},
                )
                span.set_attribute("result", str(result))
                logger.info("Temporal run successful", agent=self.name)
                return result
            except Exception as temporal_error:
                logger.error(
                    "Error in Temporal workflow",
                    agent=self.name,
                    error=str(temporal_error),
                )
                span.record_exception(temporal_error)
                raise

    def resolve_callables(self, context) -> None:
        """Resolve any callable fields in the agent instance using the provided context.

        This method resolves any callable fields in the agent instance using the provided context. It iterates over
        the agent's fields and replaces any callable objects (such as lifecycle hooks or tools) with their corresponding
        resolved values from the context. This ensures that the agent is fully configured and ready
        """
        if isinstance(self.input, Callable):
            self.input = self.input(context)
        if isinstance(self.output, Callable):
            self.output = self.output(context)
        if isinstance(self.description, Callable):
            self.description = self.description(context)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the FlockAgent instance to a dictionary.

        This method converts the entire agent instance—including its configuration, state, and lifecycle hooks—
        into a dictionary format. It uses cloudpickle to serialize any callable objects (such as functions or
        methods), converting them into hexadecimal string representations. This ensures that the agent can be
        easily persisted, transmitted, or logged as JSON.

        The serialization process is recursive:
        - If a field is a callable (and not a class), it is serialized using cloudpickle.
        - Lists and dictionaries are processed recursively to ensure that all nested callables are properly handled.

        **Returns:**
            dict[str, Any]: A dictionary representing the FlockAgent, which includes all of its configuration data.
            This dictionary is suitable for storage, debugging, or transmission over the network.

        **Example:**
            For an agent defined as:
                name = "idea_agent",
                model = "openai/gpt-4o",
                input = "query: str | The search query, context: dict | The full conversation context",
                output = "idea: str | The generated idea"
            Calling `agent.to_dict()` might produce:
                {
                    "name": "idea_agent",
                    "model": "openai/gpt-4o",
                    "input": "query: str | The search query, context: dict | The full conversation context",
                    "output": "idea: str | The generated idea",
                    "tools": ["<serialized tool representation>"],
                    "use_cache": False,
                    "hand_off": None,
                    "termination": None,
                    ...
                }
        """

        def convert_callable(obj: Any) -> Any:
            if callable(obj) and not isinstance(obj, type):
                return cloudpickle.dumps(obj).hex()
            if isinstance(obj, list):
                return [convert_callable(item) for item in obj]
            if isinstance(obj, dict):
                return {k: convert_callable(v) for k, v in obj.items()}
            return obj

        data = self.model_dump()
        return convert_callable(data)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize a FlockAgent instance from a dictionary.

        This class method reconstructs a FlockAgent from its serialized dictionary representation, as produced
        by the `to_dict()` method. It recursively processes the dictionary to convert any serialized callables
        (stored as hexadecimal strings via cloudpickle) back into executable callable objects.

        **Arguments:**
            data (dict[str, Any]): A dictionary representation of a FlockAgent, typically produced by `to_dict()`.
                The dictionary should contain all configuration fields and state information necessary to fully
                reconstruct the agent.

        **Returns:**
            FlockAgent: An instance of FlockAgent reconstructed from the provided dictionary. The deserialized agent
            will have the same configuration, state, and behavior as the original instance.

        **Example:**
            Suppose you have the following dictionary:
                {
                    "name": "idea_agent",
                    "model": "openai/gpt-4o",
                    "input": "query: str | The search query, context: dict | The full conversation context",
                    "output": "idea: str | The generated idea",
                    "tools": ["<serialized tool representation>"],
                    "use_cache": False,
                    "hand_off": None,
                    "termination": None,
                    ...
                }
            Then, calling:
                agent = FlockAgent.from_dict(data)
            will return a FlockAgent instance with the same properties and behavior as when it was originally serialized.
        """

        def convert_callable(obj: Any) -> Any:
            if isinstance(obj, str) and len(obj) > 2:
                try:
                    return cloudpickle.loads(bytes.fromhex(obj))
                except Exception:
                    return obj
            if isinstance(obj, list):
                return [convert_callable(item) for item in obj]
            if isinstance(obj, dict):
                return {k: convert_callable(v) for k, v in obj.items()}
            return obj

        converted = convert_callable(data)
        return cls(**converted)
