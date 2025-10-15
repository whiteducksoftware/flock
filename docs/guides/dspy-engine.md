---
title: DSPy Engine Deep Dive
description: Understanding how DSPy signatures and the DSPyEngine generate contract-valid artifacts
tags:
  - dspy
  - engines
  - guide
  - advanced
  - internals
search:
  boost: 1.5
---

# DSPy Engine Deep Dive

**How does Flock's DSPyEngine turn Pydantic schemas into LLM prompts and validate outputs?**

This guide explains the magic behind `DSPyEngine` — how it dynamically creates DSPy signatures from Flock's type system, generates LLM prompts, and ensures contract-valid artifacts every time.

---

## What is DSPy?

**DSPy is a framework for programming (not prompting) language models.**

Instead of writing brittle text prompts, DSPy uses **signatures** — declarative specs that define:
1. **Input fields** - What data the LLM receives
2. **Output fields** - What data the LLM must produce
3. **Instructions** - High-level guidance (not templates)

**Example DSPy signature:**
```python
import dspy

# Signature: "question -> answer"
class QA(dspy.Signature):
    """Answer questions accurately."""
    question: str = dspy.InputField()
    answer: str = dspy.OutputField()

# Use it
qa = dspy.Predict(QA)
result = qa(question="What is 2+2?")
print(result.answer)  # "4"
```

**Key insight:** DSPy compiles signatures into optimized prompts automatically. You declare **what** you want, not **how** to prompt.

---

## Why DSPy for Flock?

Flock agents declare inputs/outputs using Pydantic models:

```python
@flock_type
class TaskInput(BaseModel):
    description: str
    priority: int

@flock_type
class Report(BaseModel):
    summary: str
    findings: list[str]
    confidence: float

agent = (
    flock.agent("analyzer")
    .consumes(TaskInput)
    .publishes(Report)
)
```

**DSPyEngine's job:**
1. Convert `TaskInput` → DSPy InputField
2. Convert `Report` → DSPy OutputField
3. Generate prompt from signatures
4. Parse LLM response into validated `Report` artifact
5. Ensure **contract compliance** (correct types, counts, validation)

---

## DSPy Signature Basics

### Simple Signature (Single Input → Single Output)

```python
# Inline syntax with semantic names
signature = dspy.Signature("question: str -> answer: str")

# Class syntax (more control)
class SimpleQA(dspy.Signature):
    """Answer the question."""
    question: str = dspy.InputField()
    answer: str = dspy.OutputField()

# Flock example with semantic names
.consumes(Task).publishes(Report)
→ task: Task -> report: Report  # Semantic! LLM understands roles
```

**Result:** LLM receives structured prompt and returns structured output.

**Key insight:** Field names like "question" and "answer" are MORE meaningful than "input" and "output"!

### Multiple Inputs

```python
# Multiple input fields
signature = dspy.Signature(
    "context: str, question: str -> answer: str"
)

# Or dict syntax
signature = dspy.Signature({
    "context": (str, dspy.InputField()),
    "question": (str, dspy.InputField()),
    "answer": (str, dspy.OutputField())
})
```

**What happens:** All input fields included in prompt, LLM processes together.

### Multiple Outputs

```python
# Multiple output fields
class Analysis(dspy.Signature):
    """Analyze the document."""
    document: str = dspy.InputField()
    summary: str = dspy.OutputField()
    sentiment: str = dspy.OutputField()
    key_points: list[str] = dspy.OutputField()
```

**What happens:** LLM generates ALL output fields in structured format.

### Fan-Out (Generating Lists)

```python
class IdeaGenerator(dspy.Signature):
    """Generate multiple ideas."""
    topic: str = dspy.InputField()
    ideas: list[str] = dspy.OutputField(
        desc="Generate exactly 10 diverse ideas"
    )
```

**What happens:** LLM generates list with specified count (enforced by description).

### Using Pydantic Models

```python
from pydantic import BaseModel

class TaskInput(BaseModel):
    description: str
    priority: int

class Report(BaseModel):
    summary: str
    findings: list[str]

# DSPy accepts Pydantic models directly!
# OLD WAY (generic):
signature = dspy.Signature({
    "input": (TaskInput, dspy.InputField()),
    "output": (Report, dspy.OutputField())
})

# NEW WAY (semantic - better!):
signature = dspy.Signature({
    "task_input": (TaskInput, dspy.InputField()),
    "report": (Report, dspy.OutputField())
})
# Field names tell the LLM what to do: "generate report from task_input"
```

**What happens:** DSPy serializes Pydantic models to JSON schema for LLM.

**Why semantic names matter:** The LLM sees field names in the prompt! "Generate report from task_input" is clearer than "generate output from input".

---

## How DSPyEngine Works (Current Implementation)

### Phase 1: Signature Preparation

**Current method:** `_prepare_signature_with_context()`

```python
def _prepare_signature_with_context(
    self,
    dspy_mod,
    *,
    description: str | None,
    input_schema: type[BaseModel] | None,
    output_schema: type[BaseModel] | None,
    has_context: bool = False,
    batched: bool = False,
) -> Any:
    """Build DSPy signature from Flock agent declaration."""

    fields = {
        "description": (str, dspy_mod.InputField()),
    }

    # Add conversation context if available
    if has_context:
        fields["context"] = (
            list,
            dspy_mod.InputField(desc="Previous conversation artifacts")
        )

    # Single input field
    if batched:
        input_type = list[input_schema] if input_schema else list[dict]
    else:
        input_type = input_schema or dict

    fields["input"] = (input_type, dspy_mod.InputField())

    # Single output field
    fields["output"] = (output_schema or dict, dspy_mod.OutputField())

    # Create signature
    signature = dspy_mod.Signature(fields)

    # Add instructions
    instruction = description or "Produce valid output matching the schema."
    if has_context:
        instruction += " Consider the conversation context."
    if batched:
        instruction += " Process the entire batch coherently."
    instruction += " Return only JSON."

    return signature.with_instructions(instruction)
```

**What gets generated (CURRENT - will be improved):**

```python
# For agent: .consumes(Task).publishes(Report)
# Signature becomes:
{
    "description": (str, InputField()),
    "input": (Task, InputField()),     # Generic name
    "output": (Report, OutputField())   # Generic name
}

# With instructions:
# "Produce valid output matching the schema. Return only JSON."
```

**What will be generated (AFTER refactor - semantic!):**

```python
# For agent: .consumes(Task).publishes(Report)
# Signature becomes:
{
    "description": (str, InputField()),
    "task": (Task, InputField()),      # Semantic! Type name → field name
    "report": (Report, OutputField())  # Semantic! Type name → field name
}

# With instructions:
# "Generate report from task. Produce valid output matching the schema. Return only JSON."
```

**Why this matters:** The LLM sees "Generate report from task" instead of "Generate output from input" - much clearer!

### Phase 2: Program Selection

```python
def _choose_program(self, dspy_mod, signature, tools):
    """Select DSPy program based on tool availability."""

    tools_list = list(tools or [])

    if tools_list:
        # ReAct: Reasoning + Acting with tool calls
        return dspy_mod.ReAct(
            signature,
            tools=tools_list,
            max_iters=self.max_tool_calls
        )

    # Predict: Direct signature execution
    return dspy_mod.Predict(signature)
```

**Programs available:**
- `dspy.Predict` - Basic LLM call with signature
- `dspy.ChainOfThought` - Adds reasoning field automatically
- `dspy.ReAct` - Adds tool use + reasoning loop

### Phase 3: Execution

```python
async def _execute_standard(
    self, dspy_mod, program, *, description: str, payload: dict
) -> Any:
    """Execute DSPy program (non-streaming)."""

    # Call program with prepared inputs
    return program(
        description=description,
        input=payload["input"],
        context=payload.get("context", [])
    )
```

**What happens:**
1. DSPy builds prompt from signature + instructions
2. LLM generates response
3. DSPy parses response into structured fields
4. Returns `Prediction` object with output fields

### Phase 4: Output Extraction

```python
def _materialize_artifacts(
    self,
    payload: dict[str, Any],
    outputs: list[AgentOutput],
    produced_by: str,
    pre_generated_id: Any = None,
) -> tuple[list[Artifact], list[str]]:
    """Convert DSPy output to Flock artifacts."""

    artifacts = []
    errors = []

    for output_decl in outputs:
        model_cls = output_decl.spec.model

        # Extract payload for this output type
        data = self._select_output_payload(
            payload,
            model_cls,
            output_decl.spec.type_name
        )

        try:
            # Validate with Pydantic
            instance = model_cls(**data)

            # Create artifact
            artifact = Artifact(
                type=output_decl.spec.type_name,
                payload=instance.model_dump(),
                produced_by=produced_by,
                id=pre_generated_id  # Preserve for streaming
            )
            artifacts.append(artifact)

        except Exception as exc:
            errors.append(str(exc))

    return artifacts, errors
```

**What happens:**
1. Extract output field from DSPy result
2. Find matching Pydantic model from agent declaration
3. Validate JSON against Pydantic schema
4. Create Flock `Artifact` with validated payload
5. Return artifacts + any validation errors

---

## The Multi-Publishes Problem

### Current Limitation

**Current implementation only supports:**
- ✅ Single input type
- ✅ Single output type
- ❌ Multiple input types
- ❌ Multiple output types
- ❌ Fan-out (generate N artifacts of same type)

**Example that DOESN'T work yet:**

```python
agent = (
    flock.agent("analyzer")
    .consumes(Task, Context)  # ❌ Two inputs
    .publishes(Summary)
    .publishes(Analysis)       # ❌ Two outputs
)
```

**Why?** Signature hardcoded to `input -> output` (singular).

### What We Need

**For multi-publishes (Phase 5 feature):**

```python
# Agent with multiple outputs
agent = (
    flock.agent("analyzer")
    .consumes(Task)
    .publishes(Summary)        # First output group
    .publishes(Analysis)       # Second output group
)

# Agent with fan-out
agent = (
    flock.agent("generator")
    .consumes(Topic)
    .publishes(Idea, fan_out=5)  # Generate 5 Ideas
)
```

**Required signature (with SEMANTIC field names!):**

```python
# For multiple outputs - semantic names!
.consumes(Task).publishes(Summary).publishes(Analysis)
→ signature = {
    "description": (str, InputField()),
    "task": (Task, InputField()),           # Semantic!
    "summary": (Summary, OutputField()),     # Semantic!
    "analysis": (Analysis, OutputField())    # Semantic!
}
# LLM sees: "Generate summary and analysis from task" ✨

# For fan-out - pluralized!
.consumes(Topic).publishes(Idea, fan_out=5)
→ signature = {
    "description": (str, InputField()),
    "topic": (Topic, InputField()),          # Semantic!
    "ideas": (list[Idea], OutputField(       # Pluralized!
        desc="Generate exactly 5 diverse ideas"
    ))
}
# LLM sees: "Generate 5 ideas from topic" ✨
```

**Key improvements:**
- ✅ "task" instead of "input" - LLM knows it's analyzing a task
- ✅ "summary", "analysis" instead of "output_0", "output_1" - LLM knows what to generate
- ✅ "ideas" (plural) for lists - natural English for multiple items
- ✅ Self-documenting signatures - just reading field names tells the story!

---

## Semantic Field Naming

**Key Innovation:** Instead of generic "input" and "output" field names, we use the **type names** as field names!

### Why Semantic Names?

**Generic approach (current):**
```python
.consumes(Idea).publishes(Movie)
→ input: Idea -> output: Movie
```

**Semantic approach (refactor):**
```python
.consumes(Idea).publishes(Movie)
→ idea: Idea -> movie: Movie  # LLM knows it's converting ideas to movies!
```

### How It Works

**Type Name → Field Name Conversion:**

```python
def _type_to_field_name(type_class: type) -> str:
    """
    Convert Pydantic model class name to snake_case field name.

    Examples:
        Movie → "movie"
        ResearchQuestion → "research_question"
        APIResponse → "api_response"
        UserAuthToken → "user_auth_token"
    """
    name = type_class.__name__
    # Convert CamelCase to snake_case
    snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    return snake_case
```

**Pluralization for Fan-Out:**

```python
def _pluralize(field_name: str) -> str:
    """
    Convert singular field name to plural for lists.

    Examples:
        "idea" → "ideas"
        "movie" → "movies"
        "analysis" → "analyses"
        "story" → "stories"
    """
    # Simple English pluralization rules
    if field_name.endswith('y'):
        return field_name[:-1] + 'ies'
    elif field_name.endswith('s'):
        return field_name + 'es'
    else:
        return field_name + 's'
```

**Collision Handling:**

```python
# Problem: Input and output are same type
.consumes(Text).publishes(Text)
→ text: Text -> text: Text  # COLLISION!

# Solution: Prefix with role when collision detected
→ input_text: Text -> output_text: Text  # Clear!
```

### Real-World Examples

**Example 1: Content Analysis**
```python
.consumes(Article).publishes(Summary, Tags, SentimentScore)

# Generated signature:
{
    "article": (Article, InputField()),
    "summary": (Summary, OutputField()),
    "tags": (Tags, OutputField()),
    "sentiment_score": (SentimentScore, OutputField())  # snake_case!
}
# LLM prompt: "Generate summary, tags, and sentiment_score from article"
```

**Example 2: Idea Generation**
```python
.consumes(BrainstormTopic).publishes(CreativeIdea, fan_out=20)

# Generated signature:
{
    "brainstorm_topic": (BrainstormTopic, InputField()),  # snake_case!
    "creative_ideas": (list[CreativeIdea], OutputField(  # pluralized!
        desc="Generate exactly 20 creative_ideas"
    ))
}
# LLM prompt: "Generate 20 creative_ideas from brainstorm_topic"
```

**Example 3: Multi-Input Processing**
```python
.consumes(MeetingNotes, PreviousDecisions, CurrentGoals)
.publishes(ActionPlan)

# Generated signature:
{
    "meeting_notes": (MeetingNotes, InputField()),
    "previous_decisions": (PreviousDecisions, InputField()),
    "current_goals": (CurrentGoals, InputField()),
    "action_plan": (ActionPlan, OutputField())
}
# LLM prompt: "Generate action_plan from meeting_notes, previous_decisions, and current_goals"
# So much clearer than "generate output from input_0, input_1, input_2"!
```

### Benefits

✅ **Better LLM Understanding** - "Generate report from task" vs "Generate output from input"
✅ **Self-Documenting** - Field names tell the transformation story
✅ **Clearer Debugging** - Traces show `summary: {...}` instead of `output_0: {...}`
✅ **Natural Language** - Plurals for lists ("ideas" not "idea")
✅ **No Extra Effort** - Automatic conversion from type names

---

## How DSPyEngine Will Support Multi-Publishes

### Step 1: Dynamic Signature Generation

**New method:** `_prepare_signature_for_output_group()`

```python
def _prepare_signature_for_output_group(
    self,
    dspy_mod,
    *,
    agent,
    inputs: EvalInputs,
    output_group: OutputGroup,
    has_context: bool = False,
) -> tuple[Any, dict[str, str]]:
    """Build dynamic signature based on output_group.

    Returns:
        (signature, field_mapping)
    """

    fields = {}
    field_mapping = {}

    # 1. Description (always present)
    fields["description"] = (str, dspy_mod.InputField())

    # 2. Context (optional)
    if has_context:
        fields["context"] = (
            list,
            dspy_mod.InputField(desc="Conversation history")
        )

    # 3. Inputs (can be multiple types)
    unique_input_types = self._get_unique_input_types(inputs.artifacts)

    for idx, (type_name, pydantic_model) in enumerate(unique_input_types):
        if len(unique_input_types) == 1:
            field_name = "input"  # Backward compat
        else:
            field_name = f"input_{idx}"

        fields[field_name] = (
            pydantic_model,
            dspy_mod.InputField(desc=f"{type_name} input")
        )
        field_mapping[field_name] = type_name

    # 4. Outputs (multiple with fan-out support)
    for idx, output_decl in enumerate(output_group.outputs):
        output_schema = output_decl.spec.model
        type_name = output_decl.spec.type_name

        # Field naming
        if len(output_group.outputs) == 1:
            field_name = "output"  # Backward compat
        else:
            field_name = f"output_{idx}"

        # Fan-out: use list[Type] for count > 1
        if output_decl.count > 1:
            output_type = list[output_schema]
            desc = (
                f"Generate exactly {output_decl.count} instances "
                f"of {type_name}. Return as valid Python list."
            )
        else:
            output_type = output_schema
            desc = f"Single {type_name} instance"

        # Override with group description if provided
        if output_decl.group_description:
            desc = f"{desc}. {output_decl.group_description}"

        fields[field_name] = (
            output_type,
            dspy_mod.OutputField(desc=desc)
        )
        field_mapping[field_name] = type_name

    # 5. Create signature with instructions
    signature = dspy_mod.Signature(fields)
    instructions = self._build_signature_instructions(
        agent, output_group, has_context
    )

    return signature.with_instructions(instructions), field_mapping
```

**Example transformation (with SEMANTIC field names!):**

```python
# Flock declaration
agent = (
    flock.agent("analyzer")
    .consumes(Task)
    .publishes(Summary)
    .publishes(Analysis)
)

# Generated DSPy signature with semantic names!
{
    "description": (str, InputField()),
    "task": (Task, InputField()),                              # Semantic!
    "summary": (Summary, OutputField(desc="Summary of task")),  # Semantic!
    "analysis": (Analysis, OutputField(desc="Analysis of task")) # Semantic!
}

# Instructions (now more natural!)
"Generate summary and analysis from task.
Process the task and produce both summary and analysis outputs.
Return only valid JSON."
```

**Why semantic names win:**
- LLM understands "generate summary from task" vs "generate output_0 from input"
- Field names appear in prompts - semantic names = better prompts!
- Debugging is easier: traces show "summary: {...}" instead of "output_0: {...}"
- Self-documenting code

### Step 2: Result Extraction (Multiple Outputs)

**New method:** `_extract_artifacts_from_result()`

```python
def _extract_artifacts_from_result(
    self,
    raw_result: Any,  # DSPy Prediction object
    output_group: OutputGroup,
    field_mapping: dict[str, str],
    agent_name: str,
    pre_generated_id: Any = None,
) -> tuple[list[Artifact], list[str]]:
    """Extract artifacts from multi-output DSPy result."""

    artifacts = []
    errors = []

    # Extract each output field
    for idx, output_decl in enumerate(output_group.outputs):
        # Find field name
        field_name = "output" if len(output_group.outputs) == 1 else f"output_{idx}"

        # Get value from DSPy result
        if hasattr(raw_result, field_name):
            field_value = getattr(raw_result, field_name)
        else:
            errors.append(f"Missing output field: {field_name}")
            continue

        # Handle fan-out (list results)
        if output_decl.count > 1:
            if not isinstance(field_value, list):
                errors.append(f"Expected list for {field_name}, got {type(field_value)}")
                continue

            # Extract each item from list
            for item in field_value:
                try:
                    artifact = self._create_artifact_from_payload(
                        item, output_decl, agent_name
                    )
                    artifacts.append(artifact)
                except Exception as exc:
                    errors.append(f"Validation failed: {exc}")

        else:
            # Single artifact
            try:
                artifact = self._create_artifact_from_payload(
                    field_value, output_decl, agent_name, pre_generated_id
                )
                artifacts.append(artifact)
            except Exception as exc:
                errors.append(f"Validation failed: {exc}")

    return artifacts, errors
```

**What happens (with semantic field names):**
1. DSPy returns `Prediction(summary=..., analysis=..., ...)` (semantic names!)
2. Extract each output field by name: "summary", "analysis"
3. Handle lists for fan-out: `Prediction(ideas=[...])` → pluralized field name
4. Validate each item with Pydantic
5. Create artifacts with validated payloads
6. Return all artifacts + errors

**Example:**
```python
# For: .publishes(Summary, Analysis)
result = Prediction(
    summary={"text": "...", "length": 100},  # Semantic field!
    analysis={"findings": [...], "score": 0.8}  # Semantic field!
)

# For: .publishes(Idea, fan_out=5)
result = Prediction(
    ideas=[                                   # Pluralized!
        {"title": "Idea 1", ...},
        {"title": "Idea 2", ...},
        {"title": "Idea 3", ...},
        {"title": "Idea 4", ...},
        {"title": "Idea 5", ...}
    ]
)
```

### Step 3: Integration

**Updated `_evaluate_internal()`:**

```python
async def _evaluate_internal(
    self,
    agent,
    ctx,
    inputs: EvalInputs,
    *,
    batched: bool,
    output_group: OutputGroup | None = None,
) -> EvalResult:

    # ... (setup same as before) ...

    # ROUTING: New path for multi-output or fan-out
    if output_group and (
        len(output_group.outputs) > 1 or
        any(o.count > 1 for o in output_group.outputs)
    ):
        # NEW: Dynamic signature
        signature, field_mapping = self._prepare_signature_for_output_group(
            dspy_mod,
            agent=agent,
            inputs=inputs,
            output_group=output_group,
            has_context=has_context,
        )
    else:
        # OLD: Backward compatibility (single input/output)
        signature = self._prepare_signature_with_context(
            dspy_mod,
            description=agent.description,
            input_schema=input_model,
            output_schema=output_model,
            has_context=has_context,
            batched=batched,
        )
        field_mapping = {"input": "input", "output": "output"}

    # ... (execution same) ...
    raw_result = await self._execute_standard(...)

    # EXTRACTION: New path for multi-output
    if output_group and len(output_group.outputs) > 1:
        artifacts, errors = self._extract_artifacts_from_result(
            raw_result,
            output_group,
            field_mapping,
            agent.name,
            pre_generated_artifact_id,
        )
    else:
        # OLD: Single output extraction
        artifacts, errors = self._materialize_artifacts(...)

    # ... (return same) ...
```

**Benefits:**
- ✅ Backward compatible (single input/output still works)
- ✅ Supports multiple outputs (output_0, output_1, ...)
- ✅ Supports fan-out (`list[Type]` with count hints)
- ✅ Type-safe (Pydantic validation throughout)
- ✅ Clear instructions (LLM knows exactly what to generate)

---

## Contract Validation

### Engine Contract

**Phase 3/4 strict validation:** Engine MUST produce exactly what was requested.

```python
# In _make_outputs_for_group()
for output_decl in output_group.outputs:
    matching_artifacts = [
        a for a in result.artifacts
        if a.type == output_decl.spec.type_name
    ]

    expected_count = output_decl.count
    actual_count = len(matching_artifacts)

    if actual_count != expected_count:
        raise ValueError(
            f"Engine contract violation: Expected {expected_count} "
            f"artifacts of {output_decl.spec.type_name}, got {actual_count}"
        )
```

**Why strict?**
- Prevents silent failures
- Catches engine bugs early
- Ensures downstream agents get expected inputs
- Makes debugging obvious

### Fan-Out Contract

**For `.publishes(Type, fan_out=N)`:**

1. **DSPy signature** specifies `list[Type]` with description "Generate exactly N instances"
2. **LLM generates** list with N items (hopefully!)
3. **Engine validates** list length matches N
4. **Pydantic validates** each item matches Type schema
5. **Filtering (where)** reduces published count (intentional)
6. **Validation (validate)** fails if any item invalid

**Flow:**

```
Agent declares: .publishes(Idea, fan_out=5)
       ↓
DSPy signature: output: list[Idea]
                desc="Generate exactly 5 diverse Ideas"
       ↓
LLM generates: [Idea1, Idea2, Idea3, Idea4, Idea5]
       ↓
Engine validates: len(result) == 5 ✅
       ↓
Pydantic validates: Each Idea matches schema ✅
       ↓
Filtering (if where clause): Maybe reduces to 3 ✅
       ↓
Published: 3 Idea artifacts to blackboard
```

---

## Best Practices

### ✅ Do

- **Let schemas drive prompts** - DSPy generates better prompts than manual ones
- **Use descriptive field names** - `customer_review` better than `input`
- **Add field descriptions** - `dspy.OutputField(desc="...")` guides LLM
- **Trust the contract** - Pydantic validation catches bad outputs
- **Test with simple cases first** - Single input/output, then add complexity

### ❌ Don't

- **Don't write prompts manually** - Let DSPy compile signatures
- **Don't skip Pydantic validation** - Type safety is your friend
- **Don't ignore errors** - Validation failures mean schema mismatch
- **Don't assume LLM perfection** - Always validate outputs
- **Don't mix concerns** - Keep agent logic separate from engine logic

---

## Common Patterns

### Pattern 1: Simple Transform

```python
# Agent: Task → Report
agent.consumes(Task).publishes(Report)

# DSPy signature (semantic!)
{
    "description": (str, InputField()),
    "task": (Task, InputField()),      # Semantic: type name → field name
    "report": (Report, OutputField())  # Semantic: type name → field name
}
# LLM prompt: "Generate report from task" ✨
```

### Pattern 2: Multi-Output Analysis

```python
# Agent: Document → Summary + Sentiment + KeyPoints
agent.consumes(Document).publishes(Summary).publishes(Sentiment).publishes(KeyPoints)

# DSPy signature (semantic - much better!)
{
    "description": (str, InputField()),
    "document": (Document, InputField()),       # Semantic!
    "summary": (Summary, OutputField()),        # Semantic!
    "sentiment": (Sentiment, OutputField()),    # Semantic!
    "key_points": (KeyPoints, OutputField())    # Semantic! (snake_case)
}
# LLM prompt: "Generate summary, sentiment, and key_points from document" ✨
```

### Pattern 3: Fan-Out Generation

```python
# Agent: Topic → 10 Ideas
agent.consumes(Topic).publishes(Idea, fan_out=10)

# DSPy signature (semantic + pluralized!)
{
    "description": (str, InputField()),
    "topic": (Topic, InputField()),                           # Semantic!
    "ideas": (list[Idea], OutputField(                        # Pluralized!
        desc="Generate exactly 10 diverse ideas"
    ))
}
# LLM prompt: "Generate 10 ideas from topic" ✨
# Notice: "ideas" (plural) for the list - natural English!
```

### Pattern 4: Conditional Publishing

```python
# Agent: Review → Chapter (only if score >= 9)
agent.consumes(Review, where=lambda r: r.score >= 9).publishes(Chapter)

# DSPy signature (same as Pattern 1)
# Filtering happens AFTER engine execution in _make_outputs_for_group()
```

---

## Debugging Tips

### Check Signature Generation

```python
# In _evaluate_internal(), add logging
logger.info(f"Generated signature: {signature.signature}")
logger.info(f"Instructions: {signature.instructions}")
logger.info(f"Fields: {list(signature.fields.keys())}")
```

**Expected output:**
```
Generated signature: description, input -> output
Instructions: Process Task and generate Report. Return only JSON.
Fields: ['description', 'input', 'output']
```

### Check LLM Output

```python
# In _normalize_output_payload(), add logging
logger.info(f"Raw LLM output: {raw}")
logger.info(f"Normalized: {json.dumps(normalized, indent=2)}")
```

**Look for:**
- ✅ Valid JSON structure
- ✅ All required fields present
- ❌ Missing fields → signature issue
- ❌ Wrong types → Pydantic will catch

### Check Artifact Creation

```python
# In _materialize_artifacts(), add logging
logger.info(f"Creating artifact: type={output_decl.spec.type_name}")
logger.info(f"Payload: {data}")
```

**Look for:**
- ✅ Payload matches Pydantic schema
- ❌ Validation errors → schema/LLM mismatch
- ❌ Missing fields → incomplete LLM response

---

## Next Steps

- **[Agent Development](agents.md)** - Build agents using DSPyEngine
- **[Components Guide](components.md)** - Customize engine behavior
- **[Blackboard Architecture](blackboard.md)** - Understand artifact flow
- **[DSPy Documentation](https://dspy-docs.vercel.app)** - Official DSPy docs

---

## Summary

**DSPyEngine transforms Flock's declarative agent API into LLM calls:**

1. **Signature Generation** - Pydantic schemas → DSPy InputField/OutputField
2. **Prompt Compilation** - DSPy generates optimized prompts automatically
3. **LLM Execution** - Structured generation with retry/streaming support
4. **Output Validation** - Pydantic ensures type safety
5. **Contract Enforcement** - Strict count validation prevents silent failures

**The magic:** You declare **what** (types), DSPy figures out **how** (prompts), Pydantic ensures **correctness** (validation).

**Future enhancement:** Multi-output and fan-out support via dynamic signature generation with **semantic field naming** (coming soon!).

---

*Last updated: 2025-10-15*
*Updated with semantic field naming: 2025-10-15*
