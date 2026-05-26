---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Tools 🔧

Tools are **single functions** that an evaluator can call to perform tasks the LLM cannot (or should not) handle by itself – e.g. web scraping, database queries, or calling another API.

---

## 1. Defining a Tool

```python
from flock.core import flock_tool

@flock_tool
def get_web_content_as_markdown(url: str) -> str:
    """Fetch a web page and convert it to Markdown."""
    import requests, markdownify  # lightweight example
    html = requests.get(url, timeout=10).text
    return markdownify.markdownify(html)
```

Decorating with `@flock_tool` registers the function in the **global registry** so any agent can reference it by symbol.

---

## 2. Using Tools in Agents

```python
agent = FlockFactory.create_default_agent(
    name="page_analyser",
    input="url: str",
    output="title: str, headings: list[str]",
    tools=[get_web_content_as_markdown],
)
```

Inside your evaluator you simply call the function:

```python
content = await tools.get_web_content_as_markdown(inputs["url"])
```

The DeclarativeEvaluator automatically injects **function docs** into the prompt so the LLM knows when/how to call them.

---

## 3. Tool Signature Rules

* Use **type hints** – they become part of the prompt + allow runtime validation.
* Keep I/O **JSON-serialisable**; complex objects should be reduced to primitives.
* Raise normal Python exceptions; they propagate to `on_error`.

---

## 4. Security Considerations

* Be cautious when exposing file-system or shell operations.
* Prefer *allow-lists* over *deny-lists* when building wrappers.
* Use the `enable_temporal` sandbox if you need strict isolation.

---

That wraps up the components trilogy!  Head over to [Deployment](../deployment/index.md) to see how to ship your flock.
