# src/flock/webapp/app/api/execution.py
import asyncio
import html
import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import markdown2  # Import markdown2
from fastapi import (  # Ensure Form and HTTPException are imported
    APIRouter,
    Depends,
    Form,
    Request,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from werkzeug.utils import secure_filename

from flock.webapp.app.services.feedback_file_service import (
    create_csv_feedback_file,
    create_csv_feedback_file_for_agent,
    create_xlsx_feedback_file,
    create_xlsx_feedback_file_for_agent,
)

if TYPE_CHECKING:
    from flock.core.flock import Flock


from flock.core.logging.logging import (
    get_logger as get_flock_logger,  # For logging within the new endpoint
)
from flock.core.util.splitter import parse_schema

# Import the dependency to get the current Flock instance
from flock.webapp.app.dependencies import (
    get_flock_instance,
    get_optional_flock_instance,
    get_shared_link_store,
)

# Service function now takes app_state
from flock.webapp.app.services.sharing_store import SharedLinkStoreInterface

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# Add markdown2 filter to Jinja2 environment for this router
def markdown_filter(text):
    return markdown2.markdown(text, extras=["tables", "fenced-code-blocks"])


templates.env.filters["markdown"] = markdown_filter


class ExecutionStreamManager:
    """In-memory tracker for live streaming sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def create_session(self) -> tuple[str, asyncio.Queue]:
        run_id = uuid.uuid4().hex
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._sessions[run_id] = queue
        return run_id, queue

    async def get_queue(self, run_id: str) -> asyncio.Queue | None:
        async with self._lock:
            return self._sessions.get(run_id)

    async def remove_session(self, run_id: str) -> None:
        async with self._lock:
            self._sessions.pop(run_id, None)


execution_stream_manager = ExecutionStreamManager()
stream_logger = get_flock_logger("webapp.execution.stream")


async def _execute_agent_with_stream(
    run_id: str,
    queue: asyncio.Queue,
    start_agent_name: str,
    inputs: dict[str, Any],
    app_state: Any,
    template_context: dict[str, Any],
) -> None:
    """Run the requested agent while forwarding streaming chunks to the UI."""

    completed = False

    def emit(payload: dict[str, Any]) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            stream_logger.warning(
                "Dropping streaming payload for run %s due to full queue", run_id
            )

    async def terminate_with_error(message: str) -> None:
        emit({"type": "error", "message": message})
        await finalize_stream()

    async def finalize_stream() -> None:
        nonlocal completed
        if not completed:
            emit({"type": "complete"})
            completed = True
        await queue.put(None)

    current_flock: "Flock | None" = getattr(app_state, "flock_instance", None)
    run_store: RunStore | None = getattr(app_state, "run_store", None)

    if not current_flock:
        stream_logger.error("Stream run aborted: no flock loaded in app state.")
        await terminate_with_error("No Flock loaded in the application.")
        return

    agent = current_flock.agents.get(start_agent_name)
    if not agent:
        stream_logger.error(
            "Stream run aborted: agent '%s' not found in flock '%s'.",
            start_agent_name,
            current_flock.name,
        )
        await terminate_with_error(
            f"Agent '{html.escape(str(start_agent_name))}' not found."
        )
        return

    evaluator = getattr(agent, "evaluator", None)
    previous_callbacks: list[Any] | None = None
    original_stream_setting: bool | None = None

    if evaluator is not None:
        previous_callbacks = list(evaluator.config.stream_callbacks or [])
        original_stream_setting = getattr(evaluator.config, "stream", False)

        def stream_callback(message: Any) -> None:
            chunk = getattr(message, "chunk", None)
            signature_field = getattr(message, "signature_field_name", None)
            if chunk is None:
                return
            emit(
                {
                    "type": "token",
                    "chunk": str(chunk),
                    "field": signature_field,
                }
            )

        evaluator.config.stream_callbacks = [
            *previous_callbacks,
            stream_callback,
        ]
        if not original_stream_setting:
            evaluator.config.stream = True
    else:
        emit(
            {
                "type": "status",
                "message": "Streaming not available for this agent; results will appear when the run completes.",
            }
        )

    try:
        emit(
            {
                "type": "status",
                "message": f"Running agent '{start_agent_name}'...",
            }
        )
        result_data = await current_flock.run_async(
            agent=start_agent_name, input=inputs, box_result=False
        )

        if run_store and hasattr(run_store, "add_run_details"):
            run_identifier = (
                result_data.get("run_id", run_id)
                if isinstance(result_data, dict)
                else run_id
            )
            run_store.add_run_details(
                run_id=run_identifier,
                agent_name=start_agent_name,
                inputs=inputs,
                outputs=result_data,
            )

        encoded_result = jsonable_encoder(result_data)
        raw_json = json.dumps(
            encoded_result, indent=2, ensure_ascii=False
        ).replace("\\n", "\n")

        template = templates.get_template("partials/_results_display.html")
        final_html = template.render(
            {
                **template_context,
                "result": result_data,
                "result_raw_json": raw_json,
            }
        )

        emit(
            {
                "type": "final",
                "html": final_html,
                "result": encoded_result,
                "raw_json": raw_json,
            }
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        stream_logger.error(
            "Streamed execution for agent '%s' failed: %s",
            start_agent_name,
            exc,
            exc_info=True,
        )
        await terminate_with_error(f"An error occurred: {html.escape(str(exc))}")
        return
    finally:
        if evaluator is not None:
            if previous_callbacks is not None:
                evaluator.config.stream_callbacks = previous_callbacks
            if original_stream_setting is not None:
                evaluator.config.stream = original_stream_setting
    await finalize_stream()


@router.get("/htmx/execution-form-content", response_class=HTMLResponse)
async def htmx_get_execution_form_content(
    request: Request,
    current_flock: "Flock | None" = Depends(
        get_optional_flock_instance
    ),  # Use optional if form can show 'no flock'
):
    # flock instance is injected
    return templates.TemplateResponse(
        "partials/_execution_form.html",
        {
            "request": request,
            "flock": current_flock,  # Pass the injected flock instance
            "input_fields": [],
            "selected_agent_name": None,  # Form starts with no agent selected
        },
    )


@router.get("/htmx/agents/{agent_name}/input-form", response_class=HTMLResponse)
async def htmx_get_agent_input_form(
    request: Request,
    agent_name: str,
    current_flock: "Flock" = Depends(
        get_flock_instance
    ),  # Expect flock to be loaded
):
    # flock instance is injected
    agent = current_flock.agents.get(agent_name)
    if not agent:
        return HTMLResponse(
            f"<p class='error'>Agent '{agent_name}' not found in the current Flock.</p>"
        )

    input_fields = []
    if agent.input and isinstance(agent.input, str):
        try:
            parsed_spec = parse_schema(agent.input)
            for name, type_str, description in parsed_spec:
                field_info = {
                    "name": name,
                    "type": type_str.lower(),
                    "description": description or "",
                }
                if "bool" in field_info["type"]:
                    field_info["html_type"] = "checkbox"
                elif (
                    "int" in field_info["type"] or "float" in field_info["type"]
                ):
                    field_info["html_type"] = "number"
                elif (
                    "list" in field_info["type"] or "dict" in field_info["type"]
                ):
                    field_info["html_type"] = "textarea"
                    field_info["placeholder"] = (
                        f"Enter JSON for {field_info['type']}"
                    )
                else:
                    field_info["html_type"] = "text"
                input_fields.append(field_info)
        except Exception as e:
            return HTMLResponse(
                f"<p class='error'>Error parsing input signature for {agent_name}: {e}</p>"
            )
    return templates.TemplateResponse(
        "partials/_dynamic_input_form_content.html",
        {"request": request, "input_fields": input_fields},
    )


@router.post("/htmx/run", response_class=HTMLResponse)
async def htmx_run_flock(
    request: Request,
):
    current_flock_from_state: Flock | None = getattr(
        request.app.state, "flock_instance", None
    )
    logger = get_flock_logger("webapp.execution.regular_run")

    if not current_flock_from_state:
        logger.error("HTMX Run (Regular): No Flock loaded in app_state.")
        return HTMLResponse("<p class='error'>No Flock loaded to run.</p>")

    form_data = await request.form()
    start_agent_name = form_data.get("start_agent_name")

    if not start_agent_name:
        logger.warning("HTMX Run (Regular): Starting agent not selected.")
        return HTMLResponse("<p class='error'>Starting agent not selected.</p>")

    agent = current_flock_from_state.agents.get(start_agent_name)
    if not agent:
        logger.error(
            f"HTMX Run (Regular): Agent '{start_agent_name}' not found in Flock '{current_flock_from_state.name}'."
        )
        return HTMLResponse(
            f"<p class='error'>Agent '{start_agent_name}' not found in the current Flock.</p>"
        )

    inputs = {}
    if agent.input and isinstance(agent.input, str):
        try:
            parsed_spec = parse_schema(agent.input)
            for name, type_str, _ in parsed_spec:
                form_field_name = f"agent_input_{name}"
                raw_value = form_data.get(form_field_name)
                if raw_value is None and "bool" in type_str.lower():
                    inputs[name] = False
                    continue
                if raw_value is None:
                    inputs[name] = None
                    continue
                if "int" in type_str.lower():
                    inputs[name] = int(raw_value)
                elif "float" in type_str.lower():
                    inputs[name] = float(raw_value)
                elif "bool" in type_str.lower():
                    inputs[name] = raw_value.lower() in [
                        "true",
                        "on",
                        "1",
                        "yes",
                    ]
                elif "list" in type_str.lower() or "dict" in type_str.lower():
                    inputs[name] = json.loads(raw_value)
                else:
                    inputs[name] = raw_value
        except ValueError as ve:
            logger.error(
                f"HTMX Run (Regular): Input parsing error for agent '{start_agent_name}': {ve}",
                exc_info=True,
            )
            return HTMLResponse(
                "<p class='error'>Invalid input format. Please check your input and try again.</p>"
            )
        except Exception as e_parse:
            logger.error(
                f"HTMX Run (Regular): Error processing inputs for '{start_agent_name}': {e_parse}",
                exc_info=True,
            )
            return HTMLResponse(
                f"<p class='error'>Error processing inputs for {html.escape(str(start_agent_name))}: {html.escape(str(e_parse))}</p>"
            )

    run_id, queue = await execution_stream_manager.create_session()
    stream_url = str(request.url_for("htmx_stream_run", run_id=run_id))
    root_path = request.scope.get("root_path", "")

    template_context = {
        "request": request,
        "feedback_endpoint": f"{root_path}/ui/api/flock/htmx/feedback",
        "share_id": None,
        "flock_name": current_flock_from_state.name,
        "agent_name": start_agent_name,
        "flock_definition": current_flock_from_state.to_yaml(),
    }

    asyncio.create_task(
        _execute_agent_with_stream(
            run_id=run_id,
            queue=queue,
            start_agent_name=start_agent_name,
            inputs=inputs,
            app_state=request.app.state,
            template_context=template_context,
        )
    )

    return templates.TemplateResponse(
        "partials/_streaming_results_container.html",
        {
            "request": request,
            "run_id": run_id,
            "stream_url": stream_url,
            "agent_name": start_agent_name,
            "flock_name": current_flock_from_state.name,
        },
    )


@router.get("/htmx/run-stream/{run_id}")
async def htmx_stream_run(run_id: str):
    """Server-Sent Events endpoint streaming live agent output."""

    queue = await execution_stream_manager.get_queue(run_id)
    if queue is None:
        return HTMLResponse(
            "<p class='error'>Streaming session not found or already closed.</p>",
            status_code=404,
        )

    async def event_generator():
        try:
            while True:
                payload = await queue.get()
                if payload is None:
                    yield "event: close\ndata: {}\n\n"
                    break
                data = json.dumps(payload, ensure_ascii=False)
                yield f"data: {data}\n\n"
        finally:
            await execution_stream_manager.remove_session(run_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- NEW ENDPOINT FOR SHARED RUNS ---
@router.post("/htmx/run-shared", response_class=HTMLResponse)
async def htmx_run_shared_flock(
    request: Request,
    share_id: str = Form(...),
):
    shared_logger = get_flock_logger("webapp.execution.shared_run_stateful")
    form_data = await request.form()
    start_agent_name = form_data.get("start_agent_name")

    if not start_agent_name:
        shared_logger.warning("HTMX Run Shared: Starting agent not selected.")
        return HTMLResponse(
            "<p class='error'>Starting agent not selected for shared run.</p>"
        )

    inputs: dict[str, Any] = {}
    try:
        shared_flocks_store = getattr(request.app.state, "shared_flocks", {})
        temp_flock = shared_flocks_store.get(share_id)

        if not temp_flock:
            shared_logger.error(
                f"HTMX Run Shared: Flock instance for share_id '{share_id}' not found in app.state."
            )
            return HTMLResponse(
                f"<p class='error'>Shared session not found or expired. Please try accessing the shared link again.</p>"
            )

        shared_logger.info(
            f"HTMX Run Shared: Successfully retrieved pre-loaded Flock '{temp_flock.name}' for agent '{start_agent_name}' (share_id: {share_id})."
        )

        agent = temp_flock.agents.get(start_agent_name)
        if not agent:
            shared_logger.error(
                f"HTMX Run Shared: Agent '{start_agent_name}' not found in shared Flock '{temp_flock.name}'."
            )
            return HTMLResponse(
                f"<p class='error'>Agent '{start_agent_name}' not found in the provided shared Flock definition.</p>"
            )

        if agent.input and isinstance(agent.input, str):
            parsed_spec = parse_schema(agent.input)
            for name, type_str, _ in parsed_spec:
                form_field_name = f"agent_input_{name}"
                raw_value = form_data.get(form_field_name)
                if raw_value is None and "bool" in type_str.lower():
                    inputs[name] = False
                    continue
                if raw_value is None:
                    inputs[name] = None
                    continue
                if "int" in type_str.lower():
                    inputs[name] = int(raw_value)
                elif "float" in type_str.lower():
                    inputs[name] = float(raw_value)
                elif "bool" in type_str.lower():
                    inputs[name] = raw_value.lower() in [
                        "true",
                        "on",
                        "1",
                        "yes",
                    ]
                elif "list" in type_str.lower() or "dict" in type_str.lower():
                    inputs[name] = json.loads(raw_value)
                else:
                    inputs[name] = raw_value

        shared_logger.info(
            f"HTMX Run Shared: Executing agent '{start_agent_name}' in pre-loaded Flock '{temp_flock.name}'. Inputs: {list(inputs.keys())}"
        )
        result_data = await temp_flock.run_async(
            start_agent=start_agent_name, input=inputs, box_result=False
        )
        raw_json_for_template = json.dumps(
            jsonable_encoder(
                result_data
            ),  # ← converts every nested BaseModel, datetime, etc.
            indent=2,
            ensure_ascii=False,
        )
        # Unescape newlines for proper display in HTML <pre> tag
        result_data_raw_json_str = raw_json_for_template.replace("\\n", "\n")
        shared_logger.info(
            f"HTMX Run Shared: Agent '{start_agent_name}' executed. Result keys: {list(result_data.keys()) if isinstance(result_data, dict) else 'N/A'}"
        )

    except ValueError as ve:
        shared_logger.error(
            f"HTMX Run Shared: Input parsing error for '{start_agent_name}' (share_id: {share_id}): {ve}",
            exc_info=True,
        )
        return HTMLResponse(
            f"<p class='error'>Invalid input format: {ve!s}</p>"
        )
    except Exception as e:
        shared_logger.error(
            f"HTMX Run Shared: Error during execution for '{start_agent_name}' (share_id: {share_id}): {e}",
            exc_info=True,
        )
        return HTMLResponse(
            f"<p class='error'>An unexpected error occurred: {e!s}</p>"
        )
    root_path = request.scope.get("root_path", "")

    return templates.TemplateResponse(
        "partials/_results_display.html",
        {
            "request": request,
            "result": result_data,
            "result_raw_json": result_data_raw_json_str,
            "feedback_endpoint": f"{root_path}/ui/api/flock/htmx/feedback-shared",
            "share_id": share_id,
            "flock_name": temp_flock.name,
            "agent_name": start_agent_name,
            "flock_definition": temp_flock.to_yaml(),
        },
    )


# --- Feedback endpoints ---
@router.post("/htmx/feedback", response_class=HTMLResponse)
async def htmx_submit_feedback(
    request: Request,
    reason: str = Form(...),
    expected_response: str | None = Form(None),
    actual_response: str | None = Form(None),
    flock_name: str | None = Form(None),
    agent_name: str | None = Form(None),
    flock_definition: str | None = Form(None),
    store: SharedLinkStoreInterface = Depends(get_shared_link_store),
):
    from uuid import uuid4

    from flock.webapp.app.services.sharing_models import FeedbackRecord

    record = FeedbackRecord(
        feedback_id=uuid4().hex,
        share_id=None,
        context_type="agent_run",
        reason=reason,
        expected_response=expected_response,
        actual_response=actual_response,
        flock_name=flock_name,
        agent_name=agent_name,
        flock_definition=flock_definition,
    )
    await store.save_feedback(record)
    return HTMLResponse("<p>🙏 Feedback received – thank you!</p>")


@router.post("/htmx/feedback-shared", response_class=HTMLResponse)
async def htmx_submit_feedback_shared(
    request: Request,
    share_id: str = Form(...),
    reason: str = Form(...),
    expected_response: str | None = Form(None),
    actual_response: str | None = Form(None),
    flock_definition: str | None = Form(None),
    flock_name: str | None = Form(None),
    agent_name: str | None = Form(None),
    store: SharedLinkStoreInterface = Depends(get_shared_link_store),
):
    from uuid import uuid4

    from flock.webapp.app.services.sharing_models import FeedbackRecord

    record = FeedbackRecord(
        feedback_id=uuid4().hex,
        share_id=share_id,
        context_type="agent_run",
        reason=reason,
        expected_response=expected_response,
        actual_response=actual_response,
        flock_definition=flock_definition,
        agent_name=agent_name,
        flock_name=flock_name,
    )
    await store.save_feedback(record)
    return HTMLResponse(
        "<p>🙏 Feedback received for shared run – thank you!</p>"
    )


@router.get("/htmx/feedback-download/{format}", response_class=FileResponse)
async def chat_feedback_download_all(
    request: Request,
    format: Literal["csv", "xlsx"] = "csv",
    store: SharedLinkStoreInterface = Depends(get_shared_link_store),
):
    """Download all feedback records for all agents in the current flock as a CSV file.

    This function iterates through all agents in the currently loaded flock and collects
    all feedback records for each agent, then exports them as a single CSV file.

    Args:
        request: The FastAPI request object
        store: The shared link store interface dependency

    Returns:
        FileResponse: CSV/XLSX file containing all feedback records for all agents

    Raises:
        HTTPException: If no flock is loaded or no agents are found in the flock
    """
    safe_format = secure_filename(format)
    if safe_format == "csv":
        return await create_csv_feedback_file(
            request=request,
            store=store,
            separator=","
        )
    elif safe_format == "xlsx":
        return await create_xlsx_feedback_file(
            request=request,
            store=store,
        )
    else:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="Invalid file-format specified. Valid formats are: 'csv', 'xlsx'"
        )


@router.get("/htmx/feedback-download/{agent_name}/{format}", response_class=FileResponse)
async def chat_feedback_download(
    request: Request,
    agent_name: str,
    format: Literal["csv", "xlsx"] = "csv",
    store: SharedLinkStoreInterface = Depends(get_shared_link_store),
):
    """Download all feedback records for a specific agent as a file.

    Args:
        request: The FastAPI request object
        agent_name: Name of the agent to download feedback for
        store: The shared link store interface dependency
        format: Either 'csv' or 'xlsx' the file format to use

    Returns:
        FileResponse: CSV/XLSX file containing all feedback records for the specified agent
    """
    safe_format = secure_filename(format)
    safe_agent_name = secure_filename(agent_name)
    if safe_format == "csv":
        return await create_csv_feedback_file_for_agent(
            request=request,
            store=store,
            separator=",",
            agent_name=safe_agent_name,
        )
    elif safe_format == "xlsx":
        return await create_xlsx_feedback_file_for_agent(
            request=request,
            store=store,
            agent_name=safe_agent_name,
        )
    else:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="Invalid file-format specified. Valid formats are: 'csv', 'xlsx'"
        )
