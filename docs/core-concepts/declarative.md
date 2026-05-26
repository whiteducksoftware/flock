---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Declarative Programming in Flock ✨

Most frameworks ask you to write long, brittle *prompts* or imperative code that walks the model through every step.  **Flock** flips this on its head: you describe the *contract*, not the procedure.  The evaluator turns that contract into the right LLM calls at run-time.

---

## 1. Why Declarative?

1. **Clarity** – A two-line signature communicates intent faster than a 200-line prompt.
2. **Reusability** – When you change models (say GPT-4 → Claude) you rarely touch the agent spec.
3. **Validation** – Flock can automatically type-check inputs/outputs, catch errors early, and generate OpenAPI docs.
4. **Optimisation** – The framework can inject extra instructions (few-shot examples, chain-of-thought, etc.) without polluting user code.

---

## 2. The Mini-DSL

Signatures are plain strings with optional type hints & descriptions:

```text
"query: str | The search query, top_k: int | # documents to retrieve"
```

Behind the scenes Flock parses this into a structured schema and merges it into a **system prompt** similar to:

```text
You are `search_agent`.
You must respond with a JSON object matching the following schema:
{
  "documents": list[str]
}

Guidelines:
- The `documents` field must contain exactly `top_k` results.
- ...additional instructions from modules/evaluator...
```

The spec is also turned into **Pydantic** models at runtime so the response is validated before it reaches your code.

---

## 3. Dynamic Signatures

Sometimes the shape depends on runtime settings.  Provide a **callable** that returns a signature string or model:

```python
from datetime import date

def invoice_out():
    year = date.today().year
    return (
        f"number: str | Invoice number {year}-****, "
        "amount: float, "
        "currency: str, "
        "items: list[str]"
    )

agent = FlockAgent(
    name="invoicer",
    input="order_id: str",
    output=invoice_out,
    evaluator=InvoiceEvaluator(...),
)
```

---

## 4. Going Fully-Typed with Pydantic

If you prefer proper Python types (IDE autocompletion, mypy, etc.), define models:

```python
class OrderIn(BaseModel):
    order_id: str
    include_discount: bool = False

class InvoiceOut(BaseModel):
    number: str
    amount: float
    currency: str
    items: list[str]

agent = FlockAgent(
    name="invoicer",
    input=OrderIn,
    output=InvoiceOut,
    evaluator=InvoiceEvaluator(...),
)
```

Flock will **not** expose these classes to the LLM (that would leak Python internals).  Instead it converts them to an equivalent JSON schema.

---

## 5. Prompt Composition Pipeline

1. **Base system prompt** – set by evaluator (`DeclarativeEvaluator` by default).
2. **Agent description** – `agent.description` text.
3. **Input / output schema** – rendered as JSON spec + additional guidance.
4. **Module injections** – e.g. `OutputModule` may request thought-process streaming.
5. **Tool docs** – For each tool, a short description and parameter list is appended.

The final prompt is cached (unless `use_cache=False`) for efficiency.

---

## 6. Limits & Tips

* Keep field names **snake_case** – easier to parse.
* Large nested objects are fine but remember token costs.
* Use `include_thought_process=True` in `DeclarativeEvaluatorConfig` if you need chain-of-thought output.
* The more explicit the types/descriptions, the more reliable the model's output.

---

**Next:**  See how agents chain together in [Workflows](workflows.md).
