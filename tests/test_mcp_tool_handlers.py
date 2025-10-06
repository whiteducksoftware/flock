"""Comprehensive test suite for MCP tool and type handlers.

This module tests:
- FlockMCPTool initialization and configuration
- Tool invocation with various parameter types
- Error handling scenarios
- Type handlers for different MCP types
- Type conversions and validations
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest
from mcp import Tool
from mcp.types import (
    CallToolResult,
    CancelledNotification,
    CreateMessageRequest,
    CreateMessageRequestParams,
    CreateMessageResult,
    ImageContent,
    ListRootsRequest,
    ListRootsResult,
    LoggingMessageNotification,
    LoggingMessageNotificationParams,
    ProgressNotification,
    ResourceListChangedNotification,
    ResourceUpdatedNotification,
    TextContent,
    ToolListChangedNotification,
)
from pydantic import ValidationError

from flock.mcp.tool import TYPE_MAPPING, FlockMCPTool
from flock.mcp.types import (
    ServerNotification,
    SseServerParameters,
    StdioServerParameters,
    StreamableHttpServerParameters,
    WebsocketServerParameters,
)
from flock.mcp.types.handlers import (
    handle_cancellation_notification,
    handle_incoming_exception,
    handle_incoming_request,
    handle_incoming_server_notification,
    handle_logging_message,
    handle_progress_notification,
    handle_resource_list_changed_notification,
    handle_resource_update_notification,
    handle_tool_list_changed_notification,
)


# ============================================================================
# FlockMCPTool Tests
# ============================================================================


class TestFlockMCPTool:
    """Test suite for FlockMCPTool class."""

    @pytest.fixture
    def basic_tool_data(self):
        """Basic tool configuration data."""
        return {
            "name": "test_tool",
            "agent_id": "agent_123",
            "run_id": "run_456",
            "description": "A test tool for testing",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "A message"},
                    "count": {"type": "integer", "description": "A count value"},
                },
                "required": ["message"],
            },
            "annotations": None,  # annotations is optional, use None
        }

    def test_tool_initialization(self, basic_tool_data):
        """Test basic tool initialization."""
        tool = FlockMCPTool(**basic_tool_data)
        assert tool.name == "test_tool"
        assert tool.agent_id == "agent_123"
        assert tool.run_id == "run_456"
        assert tool.description == "A test tool for testing"
        assert tool.input_schema == basic_tool_data["input_schema"]
        assert tool.annotations is None

    def test_tool_initialization_without_optional_fields(self):
        """Test tool initialization with minimal required fields."""
        minimal_data = {
            "name": "minimal_tool",
            "agent_id": "agent_min",
            "run_id": "run_min",
            "description": None,
            "input_schema": {},
            "annotations": None,
        }
        tool = FlockMCPTool(**minimal_data)
        assert tool.name == "minimal_tool"
        assert tool.description is None
        assert tool.annotations is None

    def test_from_mcp_tool(self):
        """Test conversion from MCP Tool to FlockMCPTool."""
        mcp_tool = Tool(
            name="mcp_tool",
            description="MCP tool description",
            inputSchema={
                "type": "object",
                "properties": {"param1": {"type": "string"}},
            },
        )

        flock_tool = FlockMCPTool.from_mcp_tool(mcp_tool, agent_id="agent_789", run_id="run_101")

        assert flock_tool.name == "mcp_tool"
        assert flock_tool.agent_id == "agent_789"
        assert flock_tool.run_id == "run_101"
        assert flock_tool.description == "MCP tool description"
        assert flock_tool.annotations is None

    def test_to_mcp_tool(self, basic_tool_data):
        """Test conversion from FlockMCPTool to MCP Tool."""
        flock_tool = FlockMCPTool(**basic_tool_data)
        mcp_tool = FlockMCPTool.to_mcp_tool(flock_tool)

        assert isinstance(mcp_tool, Tool)
        assert mcp_tool.name == "test_tool"
        assert mcp_tool.description == "A test tool for testing"
        assert mcp_tool.inputSchema == basic_tool_data["input_schema"]
        assert mcp_tool.annotations is None

    def test_convert_input_schema_to_tool_args(self, basic_tool_data):
        """Test JSON schema to tool args conversion."""
        tool = FlockMCPTool(**basic_tool_data)
        args, arg_types, arg_descs = tool._convert_input_schema_to_tool_args(tool.input_schema)

        assert "message" in args
        assert "count" in args
        assert arg_types["message"] == str
        assert arg_types["count"] == int
        assert "message" in arg_descs
        assert "count" in arg_descs

    @patch("flock.mcp.tool.convert_input_schema_to_tool_args")
    def test_convert_input_schema_with_exception(self, mock_convert, basic_tool_data):
        """Test schema conversion with exception handling."""
        mock_convert.side_effect = Exception("Conversion error")
        tool = FlockMCPTool(**basic_tool_data)

        args, arg_types, arg_descs = tool._convert_input_schema_to_tool_args(tool.input_schema)

        # Should return empty dicts on error
        assert args == {}
        assert arg_types == {}
        assert arg_descs == {}

    def test_convert_mcp_tool_result_text_only(self):
        """Test conversion of MCP tool result with text content only."""
        tool = FlockMCPTool(
            name="test",
            agent_id="a1",
            run_id="r1",
            description="test",
            input_schema={},
            annotations=None,
        )

        result = CallToolResult(
            content=[
                TextContent(type="text", text="Result 1"),
                TextContent(type="text", text="Result 2"),
            ],
            isError=False,
        )

        converted = tool._convert_mcp_tool_result(result)
        assert converted == ["Result 1", "Result 2"]

    def test_convert_mcp_tool_result_single_text(self):
        """Test conversion of MCP tool result with single text content."""
        tool = FlockMCPTool(
            name="test",
            agent_id="a1",
            run_id="r1",
            description="test",
            input_schema={},
            annotations=None,
        )

        result = CallToolResult(
            content=[TextContent(type="text", text="Single result")],
            isError=False,
        )

        converted = tool._convert_mcp_tool_result(result)
        assert converted == "Single result"  # Single text should be unwrapped

    def test_convert_mcp_tool_result_with_non_text(self):
        """Test conversion of MCP tool result with non-text content."""
        tool = FlockMCPTool(
            name="test",
            agent_id="a1",
            run_id="r1",
            description="test",
            input_schema={},
            annotations=None,
        )

        non_text_content = ImageContent(type="image", data="base64data", mimeType="image/png")

        result = CallToolResult(
            content=[
                TextContent(type="text", text="Text part"),
                non_text_content,
            ],
            isError=False,
        )

        converted = tool._convert_mcp_tool_result(result)
        assert converted == "Text part"  # Text content is prioritized

    def test_convert_mcp_tool_result_non_text_only(self):
        """Test conversion of MCP tool result with only non-text content."""
        tool = FlockMCPTool(
            name="test",
            agent_id="a1",
            run_id="r1",
            description="test",
            input_schema={},
            annotations=None,
        )

        non_text_content = ImageContent(type="image", data="base64data", mimeType="image/png")

        result = CallToolResult(
            content=[non_text_content],
            isError=False,
        )

        converted = tool._convert_mcp_tool_result(result)
        assert converted == [non_text_content]

    def test_convert_mcp_tool_result_with_error(self):
        """Test conversion of MCP tool result with error flag."""
        tool = FlockMCPTool(
            name="test",
            agent_id="a1",
            run_id="r1",
            description="test",
            input_schema={},
            annotations=None,
        )

        result = CallToolResult(
            content=[TextContent(type="text", text="Error occurred")],
            isError=True,
        )

        with patch("flock.mcp.tool.logger") as mock_logger:
            converted = tool._convert_mcp_tool_result(result)
            mock_logger.error.assert_called_once()
            assert "test" in mock_logger.error.call_args[0][0]

    def test_on_error_method(self):
        """Test the on_error hook method."""
        tool = FlockMCPTool(
            name="error_tool",
            agent_id="a1",
            run_id="r1",
            description="test",
            input_schema={},
            annotations=None,
        )

        result = CallToolResult(
            content=[TextContent(type="text", text="Error")],
            isError=True,
        )

        with patch("flock.mcp.tool.logger") as mock_logger:
            returned = tool.on_error(result)
            assert returned == result
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_as_dspy_tool_successful_invocation(self, basic_tool_data):
        """Test DSPy tool wrapper with successful invocation."""
        tool = FlockMCPTool(**basic_tool_data)

        mock_server = MagicMock()
        mock_server.config.name = "test_server"
        mock_server.call_tool = AsyncMock(
            return_value=CallToolResult(
                content=[TextContent(type="text", text="Success!")],
                isError=False,
            )
        )

        dspy_tool = tool.as_dspy_tool(mock_server)

        assert dspy_tool.name == "test_tool"
        assert dspy_tool.desc == "A test tool for testing"

        # Test the wrapped function
        result = await dspy_tool.func(message="Hello", count=5)
        assert result == "Success!"

        mock_server.call_tool.assert_called_once_with(
            agent_id="agent_123",
            run_id="run_456",
            name="test_tool",
            arguments={"message": "Hello", "count": 5},
        )

    @pytest.mark.asyncio
    async def test_as_dspy_tool_with_exception(self, basic_tool_data):
        """Test DSPy tool wrapper with exception handling."""
        tool = FlockMCPTool(**basic_tool_data)

        mock_server = MagicMock()
        mock_server.config.name = "failing_server"
        mock_server.call_tool = AsyncMock(side_effect=Exception("Server error"))

        dspy_tool = tool.as_dspy_tool(mock_server)

        with patch("flock.mcp.tool.logger") as mock_logger:
            # Function should not raise, but log the exception
            result = await dspy_tool.func(message="Test")
            assert result is None  # No result on exception
            mock_logger.exception.assert_called_once()

    def test_type_mapping_constants(self):
        """Test TYPE_MAPPING constants are correct."""
        assert TYPE_MAPPING["string"] == str
        assert TYPE_MAPPING["integer"] == int
        assert TYPE_MAPPING["number"] == float
        assert TYPE_MAPPING["boolean"] == bool
        assert TYPE_MAPPING["array"] == list
        assert TYPE_MAPPING["object"] == dict

    @pytest.mark.asyncio
    async def test_as_dspy_tool_with_tracing(self, basic_tool_data):
        """Test DSPy tool wrapper with OpenTelemetry tracing."""
        tool = FlockMCPTool(**basic_tool_data)

        mock_server = MagicMock()
        mock_server.config.name = "traced_server"
        mock_server.call_tool = AsyncMock(
            return_value=CallToolResult(
                content=[TextContent(type="text", text="Traced result")],
                isError=False,
            )
        )

        dspy_tool = tool.as_dspy_tool(mock_server)

        with patch("flock.mcp.tool.tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
            mock_tracer.start_as_current_span.return_value.__exit__ = Mock()

            result = await dspy_tool.func(message="Trace me")

            assert result == "Traced result"
            mock_tracer.start_as_current_span.assert_called_once_with("tool.test_tool.call")
            mock_span.set_attribute.assert_called_once_with("tool.name", "test_tool")


# ============================================================================
# Type Handlers Tests
# ============================================================================


class TestTypeHandlers:
    """Test suite for MCP type handlers."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_client(self):
        """Create a mock MCP client."""
        client = MagicMock()
        client.config.name = "test_client"
        client.invalidate_resource_contents_cache_entry = AsyncMock()
        client.invalidate_resource_list_cache = AsyncMock()
        client.invalidate_tool_cache = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_handle_incoming_exception(self, mock_logger, mock_client):
        """Test exception handler."""
        exception = Exception("Test error")

        # The implementation awaits config.name directly (which seems like a bug)
        # For testing, we need to make config.name a coroutine
        async def get_name():
            return "test_client"

        mock_client.config.name = get_name()

        await handle_incoming_exception(exception, mock_logger, mock_client)

        mock_logger.error.assert_called_once()
        assert "test_client" in mock_logger.error.call_args[0][0]
        assert "Test error" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_progress_notification(self, mock_logger):
        """Test progress notification handler."""
        from mcp.types import ProgressNotificationParams

        notification = ProgressNotification(
            method="notifications/progress",
            params=ProgressNotificationParams(
                progressToken="token123",
                progress=50,
                total=100,
                meta={"task": "processing"},
            ),
        )

        await handle_progress_notification(notification, mock_logger, "test_server")

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "PROGRESS_NOTIFICATION" in log_message
        assert "test_server" in log_message
        assert "50.0/100.0" in log_message  # Progress values are floats
        assert "token123" in log_message

    @pytest.mark.asyncio
    async def test_handle_progress_notification_without_total(self, mock_logger):
        """Test progress notification without total value."""
        from mcp.types import ProgressNotificationParams

        notification = ProgressNotification(
            method="notifications/progress",
            params=ProgressNotificationParams(
                progressToken="token456",
                progress=25,
                total=None,
                meta=None,
            ),
        )

        await handle_progress_notification(notification, mock_logger, "test_server")

        log_message = mock_logger.info.call_args[0][0]
        assert "25.0/Unknown" in log_message  # Progress value is float

    @pytest.mark.asyncio
    async def test_handle_cancellation_notification(self, mock_logger):
        """Test cancellation notification handler."""
        from mcp.types import CancelledNotificationParams

        notification = CancelledNotification(
            method="notifications/cancelled",
            params=CancelledNotificationParams(
                requestId="req123",
                reason="User cancelled",
                meta={"context": "test"},
            ),
        )

        await handle_cancellation_notification(notification, mock_logger, "test_server")

        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]
        assert "CANCELLATION_REQUEST" in log_message
        assert "req123" in log_message
        assert "User cancelled" in log_message

    @pytest.mark.asyncio
    async def test_handle_cancellation_notification_without_reason(self, mock_logger):
        """Test cancellation notification without reason."""
        from mcp.types import CancelledNotificationParams

        notification = CancelledNotification(
            method="notifications/cancelled",
            params=CancelledNotificationParams(
                requestId="req456",
                reason=None,
                meta=None,
            ),
        )

        await handle_cancellation_notification(notification, mock_logger, "test_server")

        log_message = mock_logger.warning.call_args[0][0]
        assert "no reason given" in log_message

    @pytest.mark.asyncio
    async def test_handle_resource_update_notification(self, mock_logger, mock_client):
        """Test resource update notification handler."""
        from mcp.types import ResourceUpdatedNotificationParams

        notification = ResourceUpdatedNotification(
            method="notifications/resources/updated",
            params=ResourceUpdatedNotificationParams(
                uri="file:///test/resource.txt",
                meta={"version": 2},
            ),
        )

        await handle_resource_update_notification(notification, mock_logger, mock_client)

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "RESOURCE_UPDATE" in log_message
        assert "file:///test/resource.txt" in log_message

        # The URI is passed as an AnyUrl object
        mock_client.invalidate_resource_contents_cache_entry.assert_called_once()
        call_args = mock_client.invalidate_resource_contents_cache_entry.call_args
        assert str(call_args.kwargs["key"]) == "file:///test/resource.txt"

    @pytest.mark.asyncio
    async def test_handle_resource_list_changed_notification(self, mock_logger, mock_client):
        """Test resource list changed notification handler."""
        notification = ResourceListChangedNotification(
            method="notifications/resources/list_changed",
            params={"meta": {"count": 10}},  # Use dict for params
        )

        await handle_resource_list_changed_notification(notification, mock_logger, mock_client)

        mock_logger.info.assert_called_once()
        mock_client.invalidate_resource_list_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tool_list_changed_notification(self, mock_logger, mock_client):
        """Test tool list changed notification handler."""
        notification = ToolListChangedNotification(
            method="notifications/tools/list_changed",
            params={"meta": {"new_tools": 3}},  # Use dict for params
        )

        await handle_tool_list_changed_notification(notification, mock_logger, mock_client)

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "TOOLS_LIST_CHANGED" in log_message

        mock_client.invalidate_tool_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_logging_message_debug(self, mock_logger):
        """Test logging message handler for debug level."""
        params = LoggingMessageNotificationParams(
            level="debug",
            logger="remote.logger",
            data="Debug message",
            meta={"source": "test"},
        )

        await handle_logging_message(params, mock_logger, "test_server")

        mock_logger.debug.assert_called_once()
        log_message = mock_logger.debug.call_args[0][0]
        assert "remote.logger" in log_message
        assert "DEBUG" in log_message
        assert "Debug message" in log_message

    @pytest.mark.asyncio
    async def test_handle_logging_message_info(self, mock_logger):
        """Test logging message handler for info level."""
        params = LoggingMessageNotificationParams(
            level="info",
            logger="app.logger",
            data="Info message",
            meta=None,
        )

        await handle_logging_message(params, mock_logger, "test_server")

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "INFO:" in log_message

    @pytest.mark.asyncio
    async def test_handle_logging_message_notice(self, mock_logger):
        """Test logging message handler for notice level."""
        params = LoggingMessageNotificationParams(
            level="notice",
            logger="system",
            data="Notice message",
            meta={},
        )

        await handle_logging_message(params, mock_logger, "test_server")

        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "NOTICE:" in log_message

    @pytest.mark.asyncio
    async def test_handle_logging_message_alert(self, mock_logger):
        """Test logging message handler for alert level."""
        params = LoggingMessageNotificationParams(
            level="alert",
            logger="security",
            data="Alert message",
            meta={"priority": "high"},
        )

        await handle_logging_message(params, mock_logger, "test_server")

        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]
        assert "WARNING:" in log_message

    @pytest.mark.asyncio
    async def test_handle_logging_message_error(self, mock_logger):
        """Test logging message handler for error level."""
        params = LoggingMessageNotificationParams(
            level="error",
            logger="app.error",
            data="Error occurred",
            meta={},
        )

        await handle_logging_message(params, mock_logger, "test_server")

        mock_logger.error.assert_called_once()
        log_message = mock_logger.error.call_args[0][0]
        assert "ERROR:" in log_message

    @pytest.mark.asyncio
    async def test_handle_logging_message_critical(self, mock_logger):
        """Test logging message handler for critical level."""
        params = LoggingMessageNotificationParams(
            level="critical",
            logger="system.critical",
            data="Critical error",
            meta={},
        )

        await handle_logging_message(params, mock_logger, "test_server")

        mock_logger.error.assert_called_once()
        log_message = mock_logger.error.call_args[0][0]
        assert "CRITICAL:" in log_message

    @pytest.mark.asyncio
    async def test_handle_logging_message_emergency(self, mock_logger):
        """Test logging message handler for emergency level."""
        params = LoggingMessageNotificationParams(
            level="emergency",
            logger="system.emergency",
            data="Emergency!",
            meta={},
        )

        await handle_logging_message(params, mock_logger, "test_server")

        mock_logger.error.assert_called_once()
        log_message = mock_logger.error.call_args[0][0]
        assert "EMERGENCY:" in log_message

    @pytest.mark.asyncio
    async def test_handle_logging_message_unknown_logger(self, mock_logger):
        """Test logging message with unknown logger name."""
        params = LoggingMessageNotificationParams(
            level="info",
            logger=None,
            data="Message without logger",
            meta={},
        )

        await handle_logging_message(params, mock_logger, "test_server")

        log_message = mock_logger.info.call_args[0][0]
        assert "unknown_remote_logger" in log_message

    @pytest.mark.asyncio
    async def test_handle_incoming_server_notification(self, mock_logger, mock_client):
        """Test incoming server notification dispatcher."""
        # Test with LoggingMessageNotification
        log_notification = ServerNotification(
            root=LoggingMessageNotification(
                method="notifications/message",
                params=LoggingMessageNotificationParams(
                    level="info",
                    logger="test",
                    data="Test log",
                    meta={},
                ),
            )
        )

        await handle_incoming_server_notification(log_notification, mock_logger, mock_client)

        mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_incoming_server_notification_unrecognized(self, mock_logger, mock_client):
        """Test handling of unrecognized server notification."""
        # Create a mock notification type that's not in the handler map
        mock_notification = MagicMock()
        mock_notification.root = MagicMock()

        # Should not raise an error, just no-op
        await handle_incoming_server_notification(mock_notification, mock_logger, mock_client)

        # No logger methods should be called for unrecognized notification
        mock_logger.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_incoming_request_create_message(self, mock_logger):
        """Test handling CreateMessageRequest."""
        from mcp.types import ServerRequest

        mock_client = MagicMock()
        mock_client.sampling_callback = AsyncMock(
            return_value=CreateMessageResult(
                role="assistant",
                content=TextContent(type="text", text="Response"),
                model="test-model",
            )
        )

        # Create proper ServerRequest wrapper
        create_msg_req = CreateMessageRequest(
            method="sampling/createMessage",
            params=CreateMessageRequestParams(
                messages=[{"role": "user", "content": TextContent(type="text", text="Hello")}],
                systemPrompt="You are helpful",
                maxTokens=100,
            ),
        )

        mock_request = MagicMock()
        mock_request.request = ServerRequest(root=create_msg_req)
        mock_request.request_id = "req123"
        mock_request.request_meta = {}
        mock_request._session = MagicMock()
        mock_request._completed = False
        mock_request.respond = AsyncMock()
        mock_request.__enter__ = Mock(return_value=mock_request)
        mock_request.__exit__ = Mock(return_value=None)

        await handle_incoming_request(mock_request, mock_logger, mock_client)

        mock_client.sampling_callback.assert_called_once()
        mock_request.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_incoming_request_list_roots(self, mock_logger):
        """Test handling ListRootsRequest."""
        from mcp.types import Root, ServerRequest

        mock_client = MagicMock()
        mock_client.list_roots_callback = AsyncMock(
            return_value=ListRootsResult(roots=[Root(uri="file:///test", name="Test")])
        )

        # Create proper ServerRequest wrapper
        list_roots_req = ListRootsRequest(method="roots/list")

        mock_request = MagicMock()
        mock_request.request = ServerRequest(root=list_roots_req)
        mock_request.request_id = "req456"
        mock_request.request_meta = {}
        mock_request._session = MagicMock()
        mock_request._completed = False
        mock_request.respond = AsyncMock()
        mock_request.__enter__ = Mock(return_value=mock_request)
        mock_request.__exit__ = Mock(return_value=None)

        await handle_incoming_request(mock_request, mock_logger, mock_client)

        mock_client.list_roots_callback.assert_called_once()
        mock_request.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_incoming_request_with_exception(self, mock_logger):
        """Test exception handling in incoming request."""
        from mcp.types import ServerRequest

        mock_client = MagicMock()
        mock_client.sampling_callback = AsyncMock(side_effect=Exception("Callback error"))

        # Create proper ServerRequest wrapper
        create_msg_req = CreateMessageRequest(
            method="sampling/createMessage",
            params=CreateMessageRequestParams(
                messages=[{"role": "user", "content": TextContent(type="text", text="Hello")}],
                systemPrompt="Test",
                maxTokens=100,
            ),
        )

        mock_request = MagicMock()
        mock_request.request = ServerRequest(root=create_msg_req)
        mock_request.request_id = "req789"
        mock_request.request_meta = {}
        mock_request._session = MagicMock()
        mock_request._completed = False
        mock_request.respond = AsyncMock()
        mock_request.__enter__ = Mock(return_value=mock_request)
        mock_request.__exit__ = Mock(return_value=None)

        await handle_incoming_request(mock_request, mock_logger, mock_client)

        mock_logger.exception.assert_called_once()
        # Error response should be sent
        mock_request.respond.assert_called_once()
        error_response = mock_request.respond.call_args[0][0]
        # Check if it's a ClientResponse with error
        assert error_response is not None

    @pytest.mark.asyncio
    async def test_handle_incoming_request_unrecognized(self, mock_logger):
        """Test handling of unrecognized request type."""

        mock_client = MagicMock()

        # Create an unrecognized request type
        mock_request = MagicMock()
        mock_request.request = MagicMock()
        mock_request.request.root = MagicMock()  # Unrecognized request type
        mock_request.request_id = "req999"
        mock_request.request_meta = {}
        mock_request._session = MagicMock()

        # Should not raise, just no-op
        await handle_incoming_request(mock_request, mock_logger, mock_client)

        # No exception should be logged for unrecognized request
        mock_logger.exception.assert_not_called()


# ============================================================================
# ServerParameters Type Tests
# ============================================================================


class TestServerParametersTypes:
    """Test suite for ServerParameters types."""

    def test_stdio_server_parameters(self):
        """Test StdioServerParameters creation and serialization."""
        params = StdioServerParameters(
            command="python",
            args=["-m", "server"],
            env={"PATH": "/usr/bin"},
        )

        assert params.transport_type == "stdio"
        assert params.command == "python"
        assert params.args == ["-m", "server"]

        # Test serialization
        data = params.to_dict()
        assert data["transport_type"] == "stdio"
        assert data["command"] == "python"

        # Test deserialization
        new_params = StdioServerParameters.from_dict(data)
        assert new_params.command == params.command

    def test_websocket_server_parameters(self):
        """Test WebsocketServerParameters creation."""
        params = WebsocketServerParameters(url="ws://localhost:8080/mcp")

        assert params.transport_type == "websockets"
        assert params.url == "ws://localhost:8080/mcp"

        data = params.to_dict()
        assert data["transport_type"] == "websockets"
        assert data["url"] == "ws://localhost:8080/mcp"

    def test_streamable_http_server_parameters(self):
        """Test StreamableHttpServerParameters creation."""
        params = StreamableHttpServerParameters(
            url="http://localhost:8080/stream",
            headers={"Authorization": "Bearer token"},
            timeout=10,
            sse_read_timeout=600,
        )

        assert params.transport_type == "streamable_http"
        assert params.url == "http://localhost:8080/stream"
        assert params.timeout == 10
        assert params.sse_read_timeout == 600

        data = params.to_dict()
        assert data["transport_type"] == "streamable_http"
        # With no auth, the auth key still gets added with None values

    def test_streamable_http_with_auth(self):
        """Test StreamableHttpServerParameters with auth."""
        auth = httpx.BasicAuth("user", "pass")
        params = StreamableHttpServerParameters(
            url="http://localhost:8080",
            auth=auth,
        )

        assert params.auth == auth
        data = params.to_dict()

        # Auth should be serialized with implementation details
        assert "auth" in data
        assert "implementation" in data["auth"]

    def test_streamable_http_from_dict_with_auth(self):
        """Test StreamableHttpServerParameters deserialization with auth."""
        data = {
            "transport_type": "streamable_http",
            "url": "http://localhost:8080",
            "auth": {
                "implementation": {
                    "module_path": "httpx",
                    "classname": "BasicAuth",
                },
                "params": {
                    "username": "user",
                    "password": "pass",
                },
            },
        }

        params = StreamableHttpServerParameters.from_dict(data)
        assert params.url == "http://localhost:8080"
        assert isinstance(params.auth, httpx.BasicAuth)

    def test_streamable_http_from_dict_no_auth_impl(self):
        """Test StreamableHttpServerParameters with missing auth implementation."""
        data = {
            "transport_type": "streamable_http",
            "url": "http://localhost:8080",
            "auth": {
                "params": {"key": "value"},
            },
        }

        with pytest.raises(ValueError, match="No concrete implementation"):
            StreamableHttpServerParameters.from_dict(data)

    def test_sse_server_parameters(self):
        """Test SseServerParameters creation."""
        params = SseServerParameters(
            url="http://localhost:8080/sse",
            headers={"X-Custom": "header"},
            timeout=15,
        )

        assert params.transport_type == "sse"
        assert params.url == "http://localhost:8080/sse"
        assert params.timeout == 15

        data = params.to_dict()
        assert data["transport_type"] == "sse"
        # With no auth, the auth key still gets added

    def test_sse_server_parameters_with_auth(self):
        """Test SseServerParameters with authentication."""
        auth = httpx.DigestAuth("user", "pass")
        params = SseServerParameters(
            url="http://localhost:8080/sse",
            auth=auth,
        )

        data = params.to_dict()
        assert "auth" in data
        assert data["auth"]["implementation"]["class_name"] == "DigestAuth"

    def test_sse_from_dict_with_auth(self):
        """Test SseServerParameters deserialization with auth."""
        data = {
            "transport_type": "sse",
            "url": "http://localhost:8080/sse",
            "auth": {
                "implementation": {
                    "module_path": "httpx",
                    "class_name": "DigestAuth",
                },
                "params": {
                    "username": "user",
                    "password": "pass",
                },
            },
        }

        params = SseServerParameters.from_dict(data)
        assert isinstance(params.auth, httpx.DigestAuth)

    def test_server_parameters_path_type_absolute(self):
        """Test server parameters serialization with absolute paths."""
        params = StdioServerParameters(command="test", args=[])

        data = params.to_dict(path_type="absolute")
        # Should still work without auth component
        assert "transport_type" in data


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests combining tool and handler functionality."""

    @pytest.mark.asyncio
    async def test_tool_invocation_with_server_notifications(self):
        """Test tool invocation while handling server notifications."""
        # Create a tool
        tool = FlockMCPTool(
            name="integration_tool",
            agent_id="agent_int",
            run_id="run_int",
            description="Integration test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                },
            },
            annotations=None,
        )

        # Create mock server that sends notifications
        mock_server = MagicMock()
        mock_server.config.name = "integration_server"

        results_queue = []

        async def mock_call_tool(**kwargs):
            # Simulate server sending progress notifications
            results_queue.append("tool_called")
            return CallToolResult(
                content=[TextContent(type="text", text="Integration success")],
                isError=False,
            )

        mock_server.call_tool = mock_call_tool

        # Get DSPy tool and invoke it
        dspy_tool = tool.as_dspy_tool(mock_server)
        result = await dspy_tool.func(action="test")

        assert result == "Integration success"
        assert "tool_called" in results_queue

    @pytest.mark.asyncio
    async def test_concurrent_tool_invocations(self):
        """Test multiple tools being invoked concurrently."""
        tools = []
        for i in range(3):
            tool = FlockMCPTool(
                name=f"concurrent_tool_{i}",
                agent_id=f"agent_{i}",
                run_id=f"run_{i}",
                description=f"Tool {i}",
                input_schema={"type": "object", "properties": {}},
                annotations=None,
            )
            tools.append(tool)

        mock_server = MagicMock()
        mock_server.config.name = "concurrent_server"

        call_order = []

        async def mock_call_tool(agent_id, run_id, name, arguments):
            call_order.append(name)
            await asyncio.sleep(0.01)  # Simulate some work
            return CallToolResult(
                content=[TextContent(type="text", text=f"Result from {name}")],
                isError=False,
            )

        mock_server.call_tool = mock_call_tool

        # Create DSPy tools
        dspy_tools = [tool.as_dspy_tool(mock_server) for tool in tools]

        # Invoke all tools concurrently
        results = await asyncio.gather(*[dspy_tool.func() for dspy_tool in dspy_tools])

        assert len(results) == 3
        assert all("Result from concurrent_tool_" in str(r) for r in results)
        assert len(call_order) == 3


# ============================================================================
# Edge Cases and Error Scenarios
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_input_schema(self):
        """Test tool with empty input schema."""
        tool = FlockMCPTool(
            name="empty_schema",
            agent_id="a1",
            run_id="r1",
            description="Tool with empty schema",
            input_schema={},
            annotations=None,
        )

        args, arg_types, arg_descs = tool._convert_input_schema_to_tool_args({})
        assert args == {}
        assert arg_types == {}
        assert arg_descs == {}

    def test_complex_nested_schema(self):
        """Test tool with complex nested input schema."""
        complex_schema = {
            "type": "object",
            "properties": {
                "nested": {
                    "type": "object",
                    "properties": {
                        "deep": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            },
        }

        tool = FlockMCPTool(
            name="complex",
            agent_id="a1",
            run_id="r1",
            description="Complex tool",
            input_schema=complex_schema,
            annotations=None,
        )

        # Should not raise an error
        args, arg_types, arg_descs = tool._convert_input_schema_to_tool_args(complex_schema)

    @pytest.mark.asyncio
    async def test_tool_invocation_timeout_scenario(self):
        """Test tool invocation with simulated timeout."""
        tool = FlockMCPTool(
            name="timeout_tool",
            agent_id="a1",
            run_id="r1",
            description="Tool that times out",
            input_schema={"type": "object", "properties": {}},
            annotations=None,
        )

        mock_server = MagicMock()
        mock_server.config.name = "timeout_server"

        async def slow_call(**kwargs):
            await asyncio.sleep(0.1)
            return CallToolResult(
                content=[TextContent(type="text", text="Late response")],
                isError=False,
            )

        mock_server.call_tool = slow_call

        dspy_tool = tool.as_dspy_tool(mock_server)

        # Should complete normally (no actual timeout enforced in the code)
        result = await dspy_tool.func()
        assert result == "Late response"

    def test_validation_error_in_tool_creation(self):
        """Test validation errors when creating FlockMCPTool."""
        with pytest.raises(ValidationError):
            # Missing required fields
            FlockMCPTool(name="invalid")

    @pytest.mark.asyncio
    async def test_notification_handler_with_null_params(self):
        """Test notification handlers with null parameters."""
        mock_logger = MagicMock()
        mock_client = MagicMock()
        mock_client.config.name = "test_client"

        # ResourceListChangedNotification with empty params (no specific params type)
        notification = ResourceListChangedNotification(
            method="notifications/resources/list_changed",
            params={},  # Empty dict for params
        )

        mock_client.invalidate_resource_list_cache = AsyncMock()

        # Should handle gracefully
        await handle_resource_list_changed_notification(notification, mock_logger, mock_client)

        mock_logger.info.assert_called_once()
        mock_client.invalidate_resource_list_cache.assert_called_once()
