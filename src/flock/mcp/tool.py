"""Represents a MCP Tool in a format which is compatible with Flock's ecosystem."""

import warnings
from typing import Any, Self, TypeVar

from dspy import Tool as DSPyTool
from dspy.adapters.types.tool import convert_input_schema_to_tool_args
from mcp import Tool
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from opentelemetry import trace
from pydantic import BaseModel, Field

from flock.logging.logging import get_logger


logger = get_logger("mcp.tool")
tracer = trace.get_tracer(__name__)

# Suppress RuntimeWarnings about unawaited coroutines during introspection
# These warnings occur when libraries (Pydantic, copy, httpx) introspect the
# async function stored in DSPyTool. The warnings are false positives - the
# coroutine is properly awaited when the tool is actually executed by DSPy.
# warnings.filterwarnings(
#     "ignore",
#     message=r"coroutine '.*' was never awaited",
#     category=RuntimeWarning,
# )

T = TypeVar("T", bound="FlockMCPTool")

TYPE_MAPPING = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class FlockMCPTool(BaseModel):
    """Base Class for MCP Tools for Flock."""

    name: str = Field(..., description="Name of the tool")

    agent_id: str = Field(
        ..., description="Associated agent_id. Used for internal tracking."
    )

    run_id: str = Field(
        ..., description="Associated run_id. Used for internal tracking."
    )

    description: str | None = Field(
        ..., description="A human-readable description of the tool"
    )

    input_schema: dict[str, Any] = Field(
        ...,
        description="A JSON Schema object defining the expected parameters for the tool.",
    )

    annotations: ToolAnnotations | None = Field(
        ..., description="Optional additional tool information."
    )

    @classmethod
    def from_mcp_tool(cls, tool: Tool, agent_id: str, run_id: str) -> Self:
        """Convert MCP Tool to Flock Tool."""
        return cls(
            name=tool.name,
            agent_id=agent_id,
            run_id=run_id,
            description=tool.description,
            input_schema=tool.inputSchema,
            annotations=tool.annotations,
        )

    @classmethod
    def to_mcp_tool(cls, instance: Self) -> Tool | None:
        """Convert a flock mcp tool into a mcp tool."""
        return Tool(
            name=instance.name,
            description=instance.description,
            inputSchema=instance.input_schema,
            annotations=instance.annotations,
        )

    # Use DSPy's converter for JSON Schema → Tool args to stay aligned with DSPy.
    def _convert_input_schema_to_tool_args(
        self, input_schema: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        try:
            return convert_input_schema_to_tool_args(input_schema)
        except Exception as e:  # pragma: no cover - defensive
            logger.exception(
                "Failed to convert MCP tool schema to DSPy tool args: %s", e
            )
            # Fallback to empty definitions to avoid breaking execution
            return {}, {}, {}

    def _convert_mcp_tool_result(
        self, call_tool_result: CallToolResult
    ) -> str | list[Any]:
        text_contents: list[TextContent] = []
        non_text_contents = []

        for content in call_tool_result.content:
            if isinstance(content, TextContent):
                text_contents.append(content)
            else:
                non_text_contents.append(content)

        tool_content = [content.text for content in text_contents]
        if len(text_contents) == 1:
            tool_content = tool_content[0]

        if call_tool_result.isError:
            logger.error(f"MCP Tool '{self.name}' returned an error.")

        return tool_content or non_text_contents

    def on_error(self, res: CallToolResult, **kwargs) -> None:
        """Optional on error hook."""
        # leave it for now, might be useful for more sophisticated processing.
        logger.error(f"Tool: '{self.name}' on_error: Tool returned error.")
        return res

    def as_dspy_tool(self, server: Any) -> DSPyTool:
        """Wrap this tool as a DSPyTool for downstream.

        DSPy natively supports async functions - when the tool is called via
        `tool.acall()` or `tool.__call__()`, DSPy detects if the function returns
        a coroutine and handles it appropriately (see dspy.adapters.types.tool.Tool).

        Note: RuntimeWarnings about unawaited coroutines may appear during
        introspection by libraries (Pydantic, copy, httpx) when they access the
        function object. These are false positives - the coroutine is properly
        awaited when the tool is actually executed by DSPy.
        """
        args, arg_type, args_desc = self._convert_input_schema_to_tool_args(
            self.input_schema
        )

        async def func(*args, **kwargs):
            """Async function wrapper for MCP tool execution.

            DSPy's Tool class natively supports async functions - it calls this
            function and checks if the result is a coroutine, then handles it
            appropriately via tool.acall() or tool.__call__().
            """
            with tracer.start_as_current_span(f"tool.{self.name}.call") as span:
                span.set_attribute("tool.name", self.name)
                try:
                    logger.debug(f"Tool: {self.name}: getting client.")

                    server_name = server.config.name
                    logger.debug(
                        f"Tool: {self.name}: got client for server '{server_name}' for agent {self.agent_id} on run {self.run_id}"
                    )
                    logger.debug(f"Tool: {self.name}: calling server '{server_name}'")
                    result = await server.call_tool(
                        agent_id=self.agent_id,
                        run_id=self.run_id,
                        name=self.name,
                        arguments=kwargs,
                    )
                    logger.debug(
                        f"Tool: Called Tool: {self.name} on server '{server_name}'. Returning result to LLM."
                    )
                    return self._convert_mcp_tool_result(result)
                except Exception as e:
                    logger.exception(
                        f"Tool: Exception ocurred when calling tool '{self.name}': {e}"
                    )
                    span.record_exception(e)

        # DSPy natively supports async functions - it will detect the coroutine
        # and handle it via tool.acall() or tool.__call__() with async conversion
        return DSPyTool(
            func=func,
            name=self.name,
            desc=self.description,
            args=args,
            arg_types=arg_type,
            arg_desc=args_desc,
        )
