from __future__ import annotations

import ast  # Add import ast
import json
from datetime import datetime
from uuid import uuid4

import markdown2  # Added for Markdown to HTML conversion
from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from flock.core.flock import Flock
from flock.core.logging.logging import get_logger
from flock.webapp.app.dependencies import get_shared_link_store
from flock.webapp.app.main import get_base_context_web, templates
from flock.webapp.app.services.sharing_models import (
    FeedbackRecord,
    SharedLinkConfig,
)
from flock.webapp.app.services.sharing_store import SharedLinkStoreInterface

router = APIRouter()
logger = get_logger("webapp.chat")

# ---------------------------------------------------------------------------
# In-memory session store (cookie-based). Not suitable for production scale.
# ---------------------------------------------------------------------------
_chat_sessions: dict[str, list[dict[str, str]]] = {}

COOKIE_NAME = "chat_sid"


def _ensure_session(request: Request) -> tuple[str, list[dict[str, str]]]:
    """Returns (sid, history_list) tuple and guarantees cookie presence."""
    sid: str | None = request.cookies.get(COOKIE_NAME)
    if not sid:
        sid = uuid4().hex
    if sid not in _chat_sessions:
        _chat_sessions[sid] = []
    return sid, _chat_sessions[sid]


def _get_history_for_shared_chat(request: Request, share_id: str) -> list[dict[str, str]]:
    """Manages history for a shared chat session, namespaced by share_id and user's session_id."""
    user_sid: str | None = request.cookies.get(COOKIE_NAME)
    if not user_sid: # Should have been set by _ensure_session on page load
        user_sid = uuid4().hex
        # Note: This history will be ephemeral if the cookie isn't set back to the client,
        # but _ensure_session on the shared chat page load should handle cookie setting.

    # Composite key for shared chat history
    shared_session_key = f"shared_{share_id}_{user_sid}"
    if shared_session_key not in _chat_sessions:
        _chat_sessions[shared_session_key] = []
    return _chat_sessions[shared_session_key]


# ---------------------------------------------------------------------------
# Chat configuration (per app instance for non-shared, or from SharedLinkConfig for shared)
# ---------------------------------------------------------------------------


class ChatConfig(BaseModel):
    agent_name: str | None = None  # Name of the Flock agent to chat with
    message_key: str = "message"
    history_key: str = "history"
    response_key: str = "response"


# Store a single global chat config on the FastAPI app state for non-shared chat
def get_chat_config(request: Request) -> ChatConfig:
    if not hasattr(request.app.state, "chat_config"):
        request.app.state.chat_config = ChatConfig()
    return request.app.state.chat_config


# ---------------------------------------------------------------------------
# Helper for Shared Chat Context
# ---------------------------------------------------------------------------
async def _get_shared_chat_context(
    request: Request,
    share_id: str,
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)
) -> tuple[ChatConfig | None, Flock | None, SharedLinkConfig | None]:
    shared_config_db = await store.get_config(share_id)

    if not shared_config_db or shared_config_db.share_type != "chat":
        logger.warning(f"Shared chat link {share_id} not found or not a chat share type.")
        return None, None, None

    # Retrieve the pre-loaded Flock instance for this share_id
    # This is loaded by the /chat/shared/{share_id} endpoint in main.py (or will be)
    # For chat.py, we will create a specific /chat/shared/{share_id} endpoint

    loaded_flock: Flock | None = None
    if hasattr(request.app.state, 'shared_flocks') and share_id in request.app.state.shared_flocks:
        loaded_flock = request.app.state.shared_flocks[share_id]
    else:
        # Attempt to load on-the-fly if not found (e.g., direct API call without page load)
        # This is a fallback and might be slower if the Flock definition is large.
        # The main /chat/shared/{share_id} page route should pre-load this.
        try:
            from flock.core.flock import Flock as ConcreteFlock  # Local import
            loaded_flock = ConcreteFlock.from_yaml(shared_config_db.flock_definition)
            if not hasattr(request.app.state, 'shared_flocks'):
                request.app.state.shared_flocks = {}
            request.app.state.shared_flocks[share_id] = loaded_flock # Cache it
            logger.info(f"On-the-fly load of Flock for shared chat {share_id}.")
        except Exception as e_load:
            logger.error(f"Failed to load Flock from definition for shared chat {share_id}: {e_load}", exc_info=True)
            return None, None, shared_config_db


    frozen_chat_cfg = ChatConfig(
        agent_name=shared_config_db.agent_name, # agent_name from SharedLinkConfig is the chat agent
        message_key=shared_config_db.chat_message_key or "message",
        history_key=shared_config_db.chat_history_key or "history",
        response_key=shared_config_db.chat_response_key or "response",
    )
    return frozen_chat_cfg, loaded_flock, shared_config_db


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/chat", response_class=HTMLResponse, tags=["Chat"])
async def chat_page(request: Request):
    """Full-page chat UI (works even when the main UI is disabled)."""
    sid, history = _ensure_session(request)
    cfg = get_chat_config(request)
    context = get_base_context_web(request, ui_mode="standalone")
    context.update({"history": history, "chat_cfg": cfg, "chat_subtitle": f"Agent: {cfg.agent_name}" if cfg.agent_name else "Echo demo", "is_shared_chat": False, "share_id": None})
    response = templates.TemplateResponse("chat.html", context)
    # Set cookie if not already present
    if COOKIE_NAME not in request.cookies:
        response.set_cookie(COOKIE_NAME, sid, max_age=60 * 60 * 24 * 7)
    return response


@router.get("/chat/messages", response_class=HTMLResponse, tags=["Chat"], include_in_schema=False)
async def chat_history_partial(request: Request):
    """HTMX endpoint that returns the rendered message list."""
    _, history = _ensure_session(request)
    return templates.TemplateResponse(
        "partials/_chat_messages.html",
        {"request": request, "history": history, "now": datetime.now}
    )


@router.post("/chat/send", response_class=HTMLResponse, tags=["Chat"])
async def chat_send(request: Request, message: str = Form(...)):
    """Echo-back mock implementation. Adds user msg + bot reply to history."""
    _, history = _ensure_session(request)
    current_time = datetime.now().strftime('%H:%M')
    cfg = get_chat_config(request)
    history.append({"role": "user", "text": message, "timestamp": current_time})
    start_time = datetime.now()
    is_error = False # Initialize is_error

    flock_inst = getattr(request.app.state, "flock_instance", None)
    bot_agent = cfg.agent_name if cfg.agent_name else None
    bot_text: str

    if bot_agent and flock_inst and bot_agent in getattr(flock_inst, "agents", {}):
        run_input: dict = {}
        if cfg.message_key: run_input[cfg.message_key] = message
        if cfg.history_key: run_input[cfg.history_key] = [h["text"] for h in history if h.get("role") == "user" or h.get("role") == "bot"] # Simple text history

        try:
            result_dict = await flock_inst.run_async(start_agent=bot_agent, input=run_input, box_result=False)
            # Assuming result_dict might be the actual dict, or its string representation is what we need.
            # For now, we work with bot_text derived from it.
            if cfg.response_key:
                bot_text = str(result_dict.get(cfg.response_key, result_dict))
            else:
                bot_text = str(result_dict)

        except Exception as e:
            bot_text = f"Error: {e}"
            is_error = True

        if not is_error:
            original_bot_text = bot_text # Keep a copy
            formatted_as_json = False

            stripped_text = bot_text.strip()
            if (stripped_text.startswith('{') and stripped_text.endswith('}')) or \
               (stripped_text.startswith('[') and stripped_text.endswith(']')):
                try:
                    parsed_obj = json.loads(bot_text)
                    if isinstance(parsed_obj, (dict, list)):
                        pretty_json = json.dumps(parsed_obj, indent=2).replace('\\n', '\n')
                        bot_text = f'''<pre><code class="language-json">{pretty_json}</code></pre>'''
                        formatted_as_json = True
                except json.JSONDecodeError:
                    try:
                        evaluated_obj = ast.literal_eval(bot_text)
                        if isinstance(evaluated_obj, (dict, list)):
                            pretty_json = json.dumps(evaluated_obj, indent=2).replace('\\n', '\n')
                            bot_text = f'''<pre><code class="language-json">{pretty_json}</code></pre>'''
                            formatted_as_json = True
                    except (ValueError, SyntaxError, TypeError):
                        pass # Fall through
                except Exception as e_json_fmt:
                    logger.error(f"Error formatting likely JSON: {e_json_fmt}. Original: {original_bot_text[:200]}", exc_info=True)
                    bot_text = original_bot_text

            if not formatted_as_json:
                try:
                    bot_text = markdown2.markdown(original_bot_text, extras=["fenced-code-blocks", "tables", "break-on-newline"])
                except Exception:
                    logger.error(f"Error during Markdown conversion for bot_text. Original: {original_bot_text[:200]}", exc_info=True)
                    bot_text = original_bot_text # Fallback to original text, will be HTML escaped by Jinja if not |safe

    else:
        # Fallback echo behavior or agent not found messages
        is_error = True # Treat these as plain text, no special formatting
        if bot_agent and not flock_inst:
            bot_text = f"Agent '{bot_agent}' configured, but no Flock loaded."
        elif bot_agent and flock_inst and bot_agent not in getattr(flock_inst, "agents", {}):
             bot_text = f"Agent '{bot_agent}' configured, but not found in the loaded Flock."
        else: # No agent configured
            bot_text = f"Echo: {message}"
            # If even echo should be markdown, remove is_error=True here and let it pass through. For now, plain.

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    history.append({
        "role": "bot",
        "text": bot_text,
        "timestamp": current_time,
        "agent": bot_agent or "echo",
        "duration_ms": duration_ms,
        "raw_json": original_bot_text if 'original_bot_text' in locals() else bot_text,
        "flock_yaml": getattr(flock_inst, 'to_yaml', lambda: "")()
    })
    # Return updated history partial
    return templates.TemplateResponse(
        "partials/_chat_messages.html",
        {"request": request, "history": history, "now": datetime.now}
    )


@router.get("/ui/htmx/chat-view", response_class=HTMLResponse, tags=["Chat"], include_in_schema=False)
async def chat_container_partial(request: Request):
    _ensure_session(request)
    return templates.TemplateResponse("partials/_chat_container.html", {"request": request})


# ---------------------------------------------------------------------------
# Chat settings management
# ---------------------------------------------------------------------------


@router.get("/ui/htmx/chat-settings-form", response_class=HTMLResponse, include_in_schema=False)
async def chat_settings_form(request: Request):
    """Returns the form for configuring chat behaviour (HTMX partial)."""
    cfg = get_chat_config(request)
    flock_inst = getattr(request.app.state, "flock_instance", None)
    input_fields, output_fields = [], []
    if cfg.agent_name and flock_inst and cfg.agent_name in flock_inst.agents:
        agent_obj = flock_inst.agents[cfg.agent_name]
        # Expect signatures like "field: type | desc, ..." or "field: type" etc.
        def _extract(sig: str):
            fields = []
            for seg in sig.split(','):
                parts = seg.strip().split(':')
                if parts:
                    fields.append(parts[0].strip())
            return [f for f in fields if f]
        input_fields = _extract(agent_obj.input) if getattr(agent_obj, 'input', '') else []
        output_fields = _extract(agent_obj.output) if getattr(agent_obj, 'output', '') else []

    context = get_base_context_web(request)
    context.update({
        "chat_cfg": cfg,
        "current_flock": flock_inst,
        "input_fields": input_fields,
        "output_fields": output_fields,
    })
    return templates.TemplateResponse("partials/_chat_settings_form.html", context)


@router.post("/chat/settings", include_in_schema=False)
async def chat_settings_submit(
    request: Request,
    agent_name: str | None = Form(default=None),
    message_key: str = Form("message"),
    history_key: str = Form("history"),
    response_key: str = Form("response"),
):
    """Handles chat settings submission and triggers a toast notification."""
    cfg = get_chat_config(request)
    cfg.agent_name = agent_name
    cfg.message_key = message_key
    cfg.history_key = history_key
    cfg.response_key = response_key

    logger.info(f"Chat settings updated: Agent: {cfg.agent_name}, MsgKey: {cfg.message_key}, HistKey: {cfg.history_key}, RespKey: {cfg.response_key}")

    toast_event = {
        "showGlobalToast": {
            "message": "Chat settings saved successfully!",
            "type": "success"
        }
    }
    headers = {"HX-Trigger": json.dumps(toast_event)}
    return Response(status_code=204, headers=headers)


# --- Stand-alone Chat HTML page access to settings --------------------------


@router.get("/chat/settings-standalone", response_class=HTMLResponse, tags=["Chat"], include_in_schema=False)
async def chat_settings_standalone(request: Request):
    """Standalone page to render chat settings (used by full-page chat HTML)."""
    cfg = get_chat_config(request)
    context = get_base_context_web(request, ui_mode="standalone")
    context.update({
        "chat_cfg": cfg,
        "current_flock": getattr(request.app.state, "flock_instance", None),
    })
    return templates.TemplateResponse("chat_settings.html", context)


# ---------------------------------------------------------------------------
# Stand-alone HTMX partials (chat view & settings) for in-page swapping
# ---------------------------------------------------------------------------


@router.get("/chat/htmx/chat-view", response_class=HTMLResponse, include_in_schema=False)
async def htmx_chat_view(request: Request):
    """Return chat container partial for standalone page reload via HTMX."""
    _ensure_session(request)
    return templates.TemplateResponse("partials/_chat_container.html", {"request": request})


@router.get("/chat/htmx/settings-form", response_class=HTMLResponse, include_in_schema=False)
async def htmx_chat_settings_partial(request: Request):
    cfg = get_chat_config(request)
    # Allow temporarily selecting agent via query param without saving
    agent_override = request.query_params.get("agent_name")
    if agent_override is not None:
        cfg = cfg.copy()
        cfg.agent_name = agent_override or None

    flock_inst = getattr(request.app.state, "flock_instance", None)
    input_fields, output_fields = [], []
    if cfg.agent_name and flock_inst and cfg.agent_name in flock_inst.agents:
        agent_obj = flock_inst.agents[cfg.agent_name]
        def _extract(sig: str):
            return [seg.strip().split(':')[0].strip() for seg in sig.split(',') if seg.strip()]
        input_fields = _extract(agent_obj.input) if getattr(agent_obj, 'input', '') else []
        output_fields = _extract(agent_obj.output) if getattr(agent_obj, 'output', '') else []

    context = {"request": request, "chat_cfg": cfg, "current_flock": flock_inst, "input_fields": input_fields, "output_fields": output_fields}
    return templates.TemplateResponse("partials/_chat_settings_form.html", context)


# ---------------------------------------------------------------------------
# Shared Chat Routes
# ---------------------------------------------------------------------------

@router.get("/chat/shared/{share_id}", response_class=HTMLResponse, tags=["Chat Sharing"])
async def page_shared_chat(
    request: Request,
    share_id: str,
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)
):
    """Serves the chat page for a shared chat session."""
    logger.info(f"Accessing shared chat page for share_id: {share_id}")

    sid, _ = _ensure_session(request) # Ensures user has a session for history tracking

    shared_config_db = await store.get_config(share_id)

    if not shared_config_db or shared_config_db.share_type != "chat":
        logger.warning(f"Shared chat link {share_id} not found or not a chat share type.")
        # Consider rendering an error template or redirecting
        error_context = get_base_context_web(request, ui_mode="standalone", error="Shared chat link is invalid or has expired.")
        return templates.TemplateResponse("error_page.html", {**error_context, "error_title": "Invalid Link"}, status_code=404)

    # Load Flock from definition and cache in app.state.shared_flocks
    loaded_flock: Flock | None = None
    if hasattr(request.app.state, 'shared_flocks') and share_id in request.app.state.shared_flocks:
        loaded_flock = request.app.state.shared_flocks[share_id]
    else:
        try:
            from flock.core.flock import Flock as ConcreteFlock
            loaded_flock = ConcreteFlock.from_yaml(shared_config_db.flock_definition)
            if not hasattr(request.app.state, 'shared_flocks'):
                request.app.state.shared_flocks = {}
            request.app.state.shared_flocks[share_id] = loaded_flock
            logger.info(f"Loaded and cached Flock for shared chat {share_id} in app.state.shared_flocks.")
        except Exception as e_load:
            logger.error(f"Fatal: Could not load Flock from definition for shared chat {share_id}: {e_load}", exc_info=True)
            error_context = get_base_context_web(request, ui_mode="standalone", error=f"Could not load the shared Flock configuration: {e_load!s}")
            return templates.TemplateResponse("error_page.html", {**error_context, "error_title": "Configuration Error"}, status_code=500)

    frozen_chat_cfg = ChatConfig(
        agent_name=shared_config_db.agent_name,
        message_key=shared_config_db.chat_message_key or "message",
        history_key=shared_config_db.chat_history_key or "history",
        response_key=shared_config_db.chat_response_key or "response",
    )

    # Get history specific to this user and this shared chat
    history = _get_history_for_shared_chat(request, share_id)

    context = get_base_context_web(request, ui_mode="standalone")
    context.update({
        "history": history, # User-specific history for this shared chat
        "chat_cfg": frozen_chat_cfg, # The "frozen" config from the share link
        "chat_subtitle": f"Shared Chat - Agent: {frozen_chat_cfg.agent_name}" if frozen_chat_cfg.agent_name else "Shared Echo Chat",
        "is_shared_chat": True,
        "share_id": share_id,
        "flock": loaded_flock # Pass flock for potential display, though backend uses cached one
    })

    response = templates.TemplateResponse("chat.html", context)
    if COOKIE_NAME not in request.cookies: # Ensure cookie is set if _ensure_session created a new one
        response.set_cookie(COOKIE_NAME, sid, max_age=60 * 60 * 24 * 7)
    return response

@router.get("/chat/messages-shared/{share_id}", response_class=HTMLResponse, tags=["Chat Sharing"], include_in_schema=False)
async def chat_history_partial_shared(request: Request, share_id: str):
    """HTMX endpoint that returns the rendered message list for a shared chat."""
    # _ensure_session called on page load, so cookie should exist for history keying
    history = _get_history_for_shared_chat(request, share_id)
    return templates.TemplateResponse(
        "partials/_chat_messages.html",
        {"request": request, "history": history, "now": datetime.now}
    )

@router.post("/chat/send-shared", response_class=HTMLResponse, tags=["Chat Sharing"])
async def chat_send_shared(
    request: Request,
    share_id: str = Form(...),
    message: str = Form(...),
    # Note: Dependencies need to be declared at the route level for FastAPI to inject them.
    # So, we re-declare get_shared_link_store here or pass it to the helper if FastAPI handles sub-dependencies.
    # For simplicity with current structure, let _get_shared_chat_context handle its own dependency.
    # We can also make _get_shared_chat_context a Depends() if preferred.
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)
):
    """Handles message sending for a shared chat session."""
    frozen_chat_cfg, flock_inst, _ = await _get_shared_chat_context(request, share_id, store)
    is_error = False # Initialize is_error

    if not frozen_chat_cfg or not flock_inst:
        # Error response if config or flock couldn't be loaded
        # This history is ephemeral as it won't be saved if the config is bad
        error_history = [{"role": "bot", "text": "Error: Shared chat configuration is invalid or Flock not found.", "timestamp": datetime.now().strftime('%H:%M')}]
        return templates.TemplateResponse(
            "partials/_chat_messages.html",
            {"request": request, "history": error_history, "now": datetime.now},
            status_code=404
        )

    history = _get_history_for_shared_chat(request, share_id)
    current_time = datetime.now().strftime('%H:%M')
    history.append({"role": "user", "text": message, "timestamp": current_time})
    start_time = datetime.now()

    bot_agent = frozen_chat_cfg.agent_name
    bot_text: str

    if bot_agent and bot_agent in getattr(flock_inst, "agents", {}):
        run_input: dict = {}
        if frozen_chat_cfg.message_key: run_input[frozen_chat_cfg.message_key] = message
        if frozen_chat_cfg.history_key: run_input[frozen_chat_cfg.history_key] = [h["text"] for h in history if h.get("role") == "user" or h.get("role") == "bot"]

        try:
            result_dict = await flock_inst.run_async(agent=bot_agent, input=run_input, box_result=False)
            if frozen_chat_cfg.response_key:
                bot_text = str(result_dict.get(frozen_chat_cfg.response_key, result_dict))
            else:
                bot_text = str(result_dict)

        except Exception as e:
            bot_text = f"Error running agent {bot_agent} in shared chat: {e}"
            is_error = True
            logger.error(f"Error in /chat/send-shared (agent: {bot_agent}, share: {share_id}): {e}", exc_info=True)

        if not is_error:
            original_bot_text = bot_text # Keep a copy
            formatted_as_json = False

            stripped_text = bot_text.strip()
            if (stripped_text.startswith('{') and stripped_text.endswith('}')) or \
               (stripped_text.startswith('[') and stripped_text.endswith(']')):
                try:
                    parsed_obj = json.loads(bot_text)
                    if isinstance(parsed_obj, (dict, list)):
                        pretty_json = json.dumps(parsed_obj, indent=2).replace('\\n', '\n')
                        bot_text = f'''<pre><code class="language-json">{pretty_json}</code></pre>'''
                        formatted_as_json = True
                except json.JSONDecodeError:
                    try:
                        evaluated_obj = ast.literal_eval(bot_text)
                        if isinstance(evaluated_obj, (dict, list)):
                            pretty_json = json.dumps(evaluated_obj, indent=2).replace('\\n', '\n')
                            bot_text = f'''<pre><code class="language-json">{pretty_json}</code></pre>'''
                            formatted_as_json = True
                    except (ValueError, SyntaxError, TypeError):
                        pass # Fall through
                except Exception as e_json_fmt:
                    logger.error(f"Error formatting likely JSON (shared chat): {e_json_fmt}. Original: {original_bot_text[:200]}", exc_info=True)
                    bot_text = original_bot_text

            if not formatted_as_json:
                try:
                    bot_text = markdown2.markdown(original_bot_text, extras=["fenced-code-blocks", "tables", "break-on-newline"])
                except Exception:
                    logger.error(f"Error during Markdown conversion for shared chat bot_text. Original: {original_bot_text[:200]}", exc_info=True)
                    bot_text = original_bot_text
    else:
        # Fallback if agent misconfigured or not found in the specific shared flock
        is_error = True # Treat these as plain text
        if bot_agent and bot_agent not in getattr(flock_inst, "agents", {}):
             bot_text = f"Agent '{bot_agent}' (shared) not found in its Flock."
        elif not bot_agent:
             bot_text = f"No agent configured for this shared chat. Echoing: {message}"
        else: # Should not happen if frozen_chat_cfg and flock_inst were valid earlier
             bot_text = f"Shared Echo: {message}"

    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    history.append({
        "role": "bot",
        "text": bot_text,
        "timestamp": current_time,
        "agent": bot_agent or "shared-echo",
        "duration_ms": duration_ms,
        "raw_json": original_bot_text if 'original_bot_text' in locals() else bot_text,
        "flock_yaml": getattr(flock_inst, 'to_yaml', lambda: "")()
    })

    return templates.TemplateResponse(
        "partials/_chat_messages.html",
        {"request": request, "history": history, "now": datetime.now}
    )

# ---------------- Feedback endpoints ----------------
@router.post("/chat/htmx/feedback", response_class=HTMLResponse, include_in_schema=False)
async def chat_feedback(request: Request,
    reason: str = Form(...),
    expected_response: str | None = Form(None),
    actual_response: str | None = Form(None),
    flock_definition: str | None = Form(None),
    agent_name: str | None = Form(None),
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)):
    from uuid import uuid4
    rec = FeedbackRecord(
        feedback_id=uuid4().hex,
        share_id=None,
        context_type="chat",
        reason=reason,
        expected_response=expected_response,
        actual_response=actual_response,
        flock_definition=flock_definition,
        agent_name=agent_name,
    )
    await store.save_feedback(rec)
    toast_event = {
        "showGlobalToast": {
            "message": "Feedback received! Thanks",
            "type": "success"
        }
    }
    headers = {"HX-Trigger": json.dumps(toast_event)}
    return Response(status_code=204, headers=headers)

@router.post("/chat/htmx/feedback-shared", response_class=HTMLResponse, include_in_schema=False)
async def chat_feedback_shared(request: Request,
    share_id: str = Form(...),
    reason: str = Form(...),
    expected_response: str | None = Form(None),
    actual_response: str | None = Form(None),
    flock_definition: str | None = Form(None),
    agent_name: str | None = Form(None),
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)):
    from uuid import uuid4
    rec = FeedbackRecord(
        feedback_id=uuid4().hex,
        share_id=share_id,
        context_type="chat",
        reason=reason,
        expected_response=expected_response,
        actual_response=actual_response,
        flock_definition=flock_definition,
        agent_name=agent_name,
    )
    await store.save_feedback(rec)
    toast_event = {
        "showGlobalToast": {
            "message": "Feedback received! Thanks",
            "type": "success"
        }
    }
    headers = {"HX-Trigger": json.dumps(toast_event)}
    return Response(status_code=204, headers=headers)

@router.get("/chat/htmx/feedback-download/", response_class=FileResponse, include_in_schema=False)
async def chat_feedback_download_all(
    request: Request,
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)
):
    """Download all feedback records for all agents."""
    import csv
    import tempfile
    from pathlib import Path


    current_flock_instance: Flock | None = getattr(
        request.app.state, "flock_instance", None
    )

    if not current_flock_instance:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400, detail="No Flock loaded to download feedback for"
        )

    all_agent_names = list(current_flock_instance.agents.keys)

    if not all_agent_names:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="No agents found in the current Flock"
        )

    all_records = []

    for agent_name in all_agent_names:
        records = await store.get_all_feedback_records_for_agent(
            agent_name=agent_name
        )

        all_records.extend(records)

    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"flock_feedback_all_agents_{timestamp}.csv"
    csv_path = Path(temp_dir) / csv_filename

    headers = [
        "feedback_id",
        "share_id",
        "context_type",
        "reason",
        "excpected_response",
        "actual_response",
        "created_at",
        "flock_name",
        "agent_name",
        "flock_definition"
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()

        for record in all_records:
            row_data = {}
            for header in headers:
                value = getattr(record, header, None)
                if header == "created_at" and value:
                    row_data[header] = (
                        value.isoformat()
                        if isinstance(value, datetime)
                        else str(value)
                    )
                else:
                    row_data[header] = str(value) if value is not None else ""
            writer.writerow(row_data)

    return FileResponse(
        path=str(csv_path),
        filename=csv_filename,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_filename}"}
    )

@router.get("/chat/htmx/feedback-download/{agent_name}", response_class=FileResponse, include_in_schema=False)
async def chat_feedback_download(
    request: Request,
    agent_name: str,
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)
):
    import csv
    import tempfile
    from pathlib import Path

    records = await store.get_all_feedback_records_for_agent(agent_name=agent_name)

    # Create a temporary CSV file
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"flock_feedback_{timestamp}.csv"
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
        "flock_definition"
    ]

    # Write records to CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()

        for record in records:
            # Convert the Pydantic model to dict and ensure all fields are present
            row_data = {}
            for header in headers:
                value = getattr(record, header, None)
                # Convert datetime to ISO string for CSV
                if header == "created_at" and value:
                    row_data[header] = value.isoformat() if isinstance(value, datetime) else str(value)
                else:
                    row_data[header] = str(value) if value is not None else ""
            writer.writerow(row_data)

    # Return FileResponse with the CSV file
    return FileResponse(
        path=str(csv_path),
        filename=csv_filename,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={csv_filename}"}
    )
