# src/flock/webapp/app/api/execution.py
import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import html
import markdown2  # Import markdown2
from fastapi import (  # Ensure Form and HTTPException are imported
    APIRouter,
    Depends,
    Form,
    Request,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

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
from flock.webapp.app.services.flock_service import (
    run_current_flock_service,
    # get_current_flock_instance IS NO LONGER IMPORTED
)
from flock.webapp.app.services.sharing_store import SharedLinkStoreInterface

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# Add markdown2 filter to Jinja2 environment for this router
def markdown_filter(text):
    return markdown2.markdown(text, extras=["tables", "fenced-code-blocks"])


templates.env.filters["markdown"] = markdown_filter


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

    result_data = await run_current_flock_service(
        start_agent_name, inputs, request.app.state
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
    root_path = request.scope.get("root_path", "")
    return templates.TemplateResponse(
        "partials/_results_display.html",
        {
            "request": request,
            "result": result_data,
            "result_raw_json": result_data_raw_json_str,
            "feedback_endpoint": f"{root_path}/ui/api/flock/htmx/feedback",
            "share_id": None,
            "flock_name": current_flock_from_state.name,
            "agent_name": start_agent_name,
            "flock_definition": current_flock_from_state.to_yaml(),
        },
    )


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
    )
    await store.save_feedback(record)
    return HTMLResponse(
        "<p>🙏 Feedback received for shared run – thank you!</p>"
    )


@router.get("/htmx/feedback-download/", response_class=FileResponse)
async def chat_feedback_download_all(
    request: Request,
    store: SharedLinkStoreInterface = Depends(get_shared_link_store),
):
    """Download all feedback records for all agents in the current flock as a CSV file.

    This function iterates through all agents in the currently loaded flock and collects
    all feedback records for each agent, then exports them as a single CSV file.

    Args:
        request: The FastAPI request object
        store: The shared link store interface dependency

    Returns:
        FileResponse: CSV file containing all feedback records for all agents

    Raises:
        HTTPException: If no flock is loaded or no agents are found in the flock
    """
    import csv
    import tempfile
    from pathlib import Path

    # Get the current flock instance to retrieve all agent names
    from flock.core.flock import Flock

    current_flock_instance: Flock | None = getattr(
        request.app.state, "flock_instance", None
    )

    if not current_flock_instance:
        # If no flock is loaded, return an error response
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400, detail="No Flock loaded to download feedback for"
        )

    # Get all agent names from the current flock
    all_agent_names = list(current_flock_instance.agents.keys())

    if not all_agent_names:
        # If no agents in the flock, return an error response
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400, detail="No agents found in the current Flock"
        )

    # Collect all feedback records from all agents
    all_records = []
    for agent_name in all_agent_names:
        records = await store.get_all_feedback_records_for_agent(
            agent_name=agent_name
        )
        all_records.extend(records)

    # Create a temporary CSV file
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"flock_feedback_all_agents_{timestamp}.csv"
    csv_path = Path(temp_dir) / csv_filename

    # Define CSV headers based on FeedbackRecord fields
    headers = [
        "feedback_id",
        "share_id",
        "context_type",
        "reason",
        "expected_response",
        "actual_response",
        "created_at",
        "flock_name",
        "agent_name",
        "flock_definition",
    ]

    # Write records to CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()

        for record in all_records:
            # Convert the Pydantic model to dict and ensure all fields are present
            row_data = {}
            for header in headers:
                value = getattr(record, header, None)
                # Convert datetime to ISO string for CSV
                if header == "created_at" and value:
                    row_data[header] = (
                        value.isoformat()
                        if isinstance(value, datetime)
                        else str(value)
                    )
                else:
                    row_data[header] = str(value) if value is not None else ""
            writer.writerow(row_data)

    # Return FileResponse with the CSV file
    return FileResponse(
        path=str(csv_path),
        filename=csv_filename,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_filename}"},
    )


@router.get("/htmx/feedback-download/{agent_name}", response_class=FileResponse)
async def chat_feedback_download(
    request: Request,
    agent_name: str,
    store: SharedLinkStoreInterface = Depends(get_shared_link_store),
):
    """Download all feedback records for a specific agent as a CSV file.

    Args:
        request: The FastAPI request object
        agent_name: Name of the agent to download feedback for
        store: The shared link store interface dependency

    Returns:
        FileResponse: CSV file containing all feedback records for the specified agent
    """
    import csv
    import tempfile
    from pathlib import Path
    from werkzeug.utils import secure_filename

    records = await store.get_all_feedback_records_for_agent(
        agent_name=agent_name
    )

    # Create a temporary CSV file
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_agent_name = secure_filename(agent_name)
    csv_filename = f"flock_feedback_{safe_agent_name}_{timestamp}.csv"
    csv_path = Path(temp_dir) / csv_filename

    # Define CSV headers based on FeedbackRecord fields
    headers = [
        "feedback_id",
        "share_id",
        "context_type",
        "reason",
        "expected_response",
        "actual_response",
        "created_at",
        "flock_name",
        "agent_name",
        "flock_definition",
    ]

    # Write records to CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()

        for record in records:
            # Convert the Pydantic model to dict and ensure all fields are present
            row_data = {}
            for header in headers:
                value = getattr(record, header, None)
                # Convert datetime to ISO string for CSV
                if header == "created_at" and value:
                    row_data[header] = (
                        value.isoformat()
                        if isinstance(value, datetime)
                        else str(value)
                    )
                else:
                    row_data[header] = str(value) if value is not None else ""
            writer.writerow(row_data)

    # Return FileResponse with the CSV file
    return FileResponse(
        path=str(csv_path),
        filename=csv_filename,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_filename}"},
    )
