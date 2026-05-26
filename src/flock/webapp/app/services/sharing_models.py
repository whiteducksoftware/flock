from datetime import datetime

from pydantic import BaseModel, Field


class SharedLinkConfig(BaseModel):
    """Configuration for a shared Flock agent execution link or chat session."""

    share_id: str = Field(..., description="Unique identifier for the shared link.")
    agent_name: str = Field(..., description="The name of the agent being shared (for run) or the chat agent (for chat).")
    flock_definition: str = Field(..., description="The YAML/JSON string definition of the Flock the agent belongs to.")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of when the link was created."
    )
    share_type: str = Field(default="agent_run", description="Type of share: 'agent_run' or 'chat'")

    # Chat-specific settings (only relevant if share_type is 'chat')
    chat_message_key: str | None = Field(None, description="Message key for chat input mapping.")
    chat_history_key: str | None = Field(None, description="History key for chat input mapping.")
    chat_response_key: str | None = Field(None, description="Response key for chat output mapping.")

    # Placeholder for future enhancement: pre-filled input values
    # input_values: Optional[Dict[str, Any]] = Field(
    #     None, description="Optional pre-filled input values for the agent."
    # )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "share_id": "abcdef123456",
                    "agent_name": "MyChatAgent",
                    "flock_definition": "name: MySharedFlock\nagents:\n  MyChatAgent:\n    input: 'message: str'\n    output: 'response: str'\n    # ... rest of flock YAML ...",
                    "created_at": "2023-10-26T10:00:00Z",
                    "share_type": "chat",
                    "chat_message_key": "user_input",
                    "chat_history_key": "conversation_history",
                    "chat_response_key": "agent_output"
                }
            ]
        }
    }

# -----------------------------------------------------------
# Feedback model (user ratings / corrections)
# -----------------------------------------------------------


class FeedbackRecord(BaseModel):
    """A user-submitted piece of feedback for an agent run or chat turn."""

    feedback_id: str = Field(..., description="Unique identifier for this feedback entry.")
    share_id: str | None = Field(None, description="If the feedback refers to a shared link, its ID; otherwise None.")
    context_type: str = Field(
        default="agent_run",
        description="Where the feedback originates (agent_run | chat | other)",
    )
    reason: str = Field(..., description="User-supplied reason / comment.")
    expected_response: str | None = Field(
        None,
        description="Desired or corrected response in JSON or plain text.",
    )
    actual_response: str | None = Field(
        None,
        description="Original response shown to the user (optional, for context).",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # When share_id is None store explicit target identifiers
    flock_name: str | None = Field(
        None,
        description="Name of the flock that produced the result when no share_id is used.",
    )
    agent_name: str | None = Field(
        None,
        description="Name of the agent or chat involved in the feedback.",
    )
    flock_definition: str | None = Field(
        None,
        description="Full YAML definition of the flock when feedback was submitted.",
    )
