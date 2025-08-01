---
hide:
  - toc
---

# 🖥️ Web UI (FastHTML)

For quick interactive testing, demonstrations, or simple internal tools, Flock can generate a basic web user interface using [FastHTML](https://fastht.ml/). This UI allows you to select agents, provide inputs through a form, and view the results directly in your browser.

## Starting the Server with UI

To enable the Web UI, simply set the `create_ui=True` flag when starting the API server:

```python
from flock.core import Flock, FlockFactory

# --- Configure your Flock and Agents ---
flock = Flock(name="My UI Flock", model="openai/gpt-4o")

greeting_agent = FlockFactory.create_default_agent(
    name="greeter",
    input="name: str | Person's name",
    output="greeting: str | A friendly greeting"
)
flock.add_agent(greeting_agent)
# ... add more agents ...

# --- Start the API Server with UI Enabled ---
if __name__ == "__main__":
    flock.start_api(
        host="127.0.0.1",
        port=8344,
        server_name="My Flock Service UI",
        create_ui=True # Enable the UI
    )
```

Now, when you run this script, not only will the REST API be available, but you can also access the Web UI by navigating your browser to:

http://127.0.0.1:8344/ui/

(Note: The API root / will typically redirect to /ui/ when the UI is enabled).

## Using the Web UI

The generated UI is straightforward:

1. **Select Starting Agent**: A dropdown menu lists all agents registered in your Flock instance. Choose the agent you want to execute.

2. **Agent Inputs**: Once you select an agent, the UI will dynamically generate input fields based on the agent's input specification string. It attempts to create appropriate HTML elements (text inputs, number inputs, checkboxes for booleans, textareas for complex types like lists/dicts). Descriptions provided in the input spec (using |) will often be used as placeholders or hints.

3. **Run Flock**: Fill in the required input fields. Click the "Run Flock" button.

4. **Result Area**: The UI will make a request to the backend API. Once the agent run completes, the formatted result will be displayed in the "Result" section below the form.

(Placeholder: Screenshot of the agent selection dropdown and dynamic input fields)

(Placeholder: Screenshot of the result area showing a formatted output table)

## How it Works (Briefly)

The UI uses:

- **FastHTML**: For building the server-side Python code that generates the HTML structure.
- **HTMX**: For handling dynamic updates (like loading agent inputs) and form submissions without full page reloads.
- **Pico.css**: For basic styling.

It communicates with the same backend REST API endpoints used for programmatic interaction, providing a visual layer over the API.

The Web UI is excellent for:

- Quickly testing different agents and inputs.
- Demonstrating Flock capabilities without writing client code.
- Simple internal tools where a basic web interface is sufficient.


## Collecting Feedback

Sometimes, you might need to collect feedback on the
performance of your agents from your users as you iteratively refine your application.

The WebUI offers a simple feedback-mechanism, allowing
you to collect feedback from your users or team as you 
iteratively refine your application.

You can retrieve a CSV-File with the collected
feedbacks for a specific agent by selecting 
the `Download feedback for the selected agent...`
option below the `Run Flock`-Button.
