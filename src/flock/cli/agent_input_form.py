from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Static


class AgentInputForm(Static):
    """A mask for agent input that dynamically presents the key fields in an elegant layout."""

    def compose(self) -> ComposeResult:
        yield Label("Agent Input Form", id="form-title")
        with Vertical(id="form-container"):
            # Agent Name
            with Horizontal():
                yield Label("Name:", id="name-label")
                self.name_input = Input(
                    placeholder="Agent Name", id="agent-name"
                )
                yield self.name_input
            # Model Field
            with Horizontal():
                yield Label("Model:", id="model-label")
                self.model_input = Input(
                    placeholder="e.g., openai/gpt-4o", id="agent-model"
                )
                yield self.model_input
            # Description Field
            with Horizontal():
                yield Label("Description:", id="description-label")
                self.description_input = Input(
                    placeholder="Short description", id="agent-description"
                )
                yield self.description_input
            # Input Specification Field
            with Horizontal():
                yield Label("Input Spec:", id="input-label")
                self.input_input = Input(
                    placeholder="e.g., query: str | search query",
                    id="agent-input",
                )
                yield self.input_input
            # Output Specification Field
            with Horizontal():
                yield Label("Output Spec:", id="output-label")
                self.output_input = Input(
                    placeholder="e.g., result: str | generated result",
                    id="agent-output",
                )
                yield self.output_input
            # Use Cache Toggle (optional)
            with Horizontal():
                yield Label("Use Cache:", id="use-cache-label")
                self.cache_checkbox = Checkbox(
                    label="Enable Cache", id="agent-use-cache"
                )
                yield self.cache_checkbox
            # (Optional additional fields like tools, hand_off, etc. can be added here.)
            # Save and Cancel Buttons
            with Horizontal():
                yield Button("Save Agent", id="save-agent")
                yield Button("Cancel", id="cancel-agent")
