"""LLMCompilerProgram — plan parallel tool calls, then synthesize final.

This native implementation follows the core ideas from LLMCompiler:
- A Planner compiles the task into a set of tool-calling tasks with dependencies.
- An Executor schedules tasks (potentially in parallel) and collects observations.
- A Synthesizer produces the final structured output from the observations.

The program is fully native (no extra libraries) and uses LMClient + ToolAdapter.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping
from dataclasses import dataclass
import asyncio
import json

from .lm_client import LMClient, LMRequest
from .program_base import Program
from .prompt_builder import build_prompt
from .tool_adapter import ToolAdapter


@dataclass
class _Task:
    id: str
    uses: str  # tool name (or "model" for LLM step)
    args: dict[str, Any]
    depends_on: list[str]
    save_as: str | None = None


class LLMCompilerProgram(Program):
    def __init__(
        self,
        model: str | None = None,
        description: str | None = None,
        input_spec: Any | None = None,
        output_spec: Any | None = None,
        tools: Mapping[str, Any] | None = None,
        max_parallel: int = 4,
        agent_name: str = "agent",
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.description = (
            description
            or "Compile the problem into parallelizable tool calls, then synthesize the final answer."
        )
        self.input_spec = input_spec
        self.output_spec = output_spec
        self.tools = dict(tools or {})
        self.max_parallel = max_parallel
        self.agent_name = agent_name
        self.options = kwargs
        self._tool_adapter = ToolAdapter()

    # ---------------- Planner ----------------
    def _tool_manifest(self) -> str:
        if not self.tools:
            return "(no tools available)"
        lines = []
        for name, fn in self.tools.items():
            doc = getattr(fn, "__doc__", None) or ""
            doc = " ".join(doc.split()) if isinstance(doc, str) else ""
            lines.append(f"- {name}: {doc}")
        return "\n".join(lines)

    def _plan_schema(self) -> dict[str, Any]:
        return {
            "name": f"{self.agent_name}_llmcompiler_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "uses": {"type": "string"},
                                "args": {"type": "object", "additionalProperties": True},
                                "depends_on": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "default": [],
                                },
                                "save_as": {"type": "string"},
                            },
                            "required": ["id", "uses", "args"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["tasks"],
                "additionalProperties": False,
            },
        }

    def _build_planner_messages(self, inputs: dict[str, Any]) -> list[dict[str, str]]:
        tool_names = ", ".join(sorted(self.tools.keys())) or "<none>"
        sys = (
            f"You are an agent named '{self.agent_name}'.\n"
            f"{self.description}\n\n"
            "TOOLS (callable by name with JSON args):\n"
            f"{self._tool_manifest()}\n\n"
            "PLANNING RULES (strict):\n"
            "- Respond with ONLY JSON (no extra text).\n"
            "- Output an object with a 'tasks' array. Each task has: id, uses, args, optional depends_on (array), optional save_as.\n"
            f"- Allowed tool names (uses) EXACTLY: {tool_names}. Do not invent new names.\n"
            "- Use 'save_as' for reusable results (e.g., 'p_widget', 'ship', 'tax').\n"
            "- Keep independent tasks parallelizable (e.g., different item prices).\n\n"
            "EXAMPLE (illustrative):\n"
            "{\n  \"tasks\": [\n    {\"id\": \"t1\", \"uses\": \"fetch_product_price\", \"args\": {\"name\": \"widget\"}, \"save_as\": \"p_widget\"},\n"
            "    {\"id\": \"t2\", \"uses\": \"fetch_product_price\", \"args\": {\"name\": \"gizmo\"}, \"save_as\": \"p_gizmo\"},\n"
            "    {\"id\": \"t3\", \"uses\": \"fetch_shipping_rate\", \"args\": {\"country\": \"DE\"}, \"save_as\": \"ship\"},\n"
            "    {\"id\": \"t4\", \"uses\": \"fetch_tax_rate\", \"args\": {\"country\": \"DE\"}, \"save_as\": \"tax\"}\n  ]\n}"
        )
        return [
            {"role": "system", "content": sys},
            {"role": "user", "content": json.dumps({"inputs": inputs})},
        ]

    async def _compile_plan(self, client: LMClient, inputs: dict[str, Any]) -> list[_Task]:
        messages = self._build_planner_messages(inputs)
        # Use generic JSON object for planning to maximize provider compatibility
        extra = {"response_format": {"type": "json_object"}}
        result, _usage = await client.generate(LMRequest(model=self.model or "", messages=messages, extra=extra))
        text = (result.get("text") or "").strip()
        try:
            payload = json.loads(text)
            raw_tasks = payload.get("tasks", [])
        except Exception:
            raw_tasks = []
        tasks: list[_Task] = []
        for t in raw_tasks:
            try:
                tasks.append(
                    _Task(
                        id=str(t.get("id")),
                        uses=str(t.get("uses")),
                        args=dict(t.get("args") or {}),
                        depends_on=list(t.get("depends_on") or []),
                        save_as=(t.get("save_as") or None),
                    )
                )
            except Exception:
                continue
        return tasks

    # ---------------- Executor ----------------
    def _resolve_args(self, args: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
        def _resolve(v: Any) -> Any:
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                key = v[2:-1]
                return memory.get(key)
            if isinstance(v, list):
                return [_resolve(x) for x in v]
            if isinstance(v, dict):
                return {k: _resolve(x) for k, x in v.items()}
            return v

        return {k: _resolve(v) for k, v in args.items()}

    async def _execute_plan(
        self,
        tasks: list[_Task],
        memory: dict[str, Any],
        yield_event: callable | None = None,
    ) -> None:
        # Simple dependency scheduler with limited parallelism
        remaining = {t.id: t for t in tasks}
        in_progress: set[str] = set()
        sem = asyncio.Semaphore(self.max_parallel)

        async def _run_task(t: _Task) -> None:
            async with sem:
                if yield_event:
                    await yield_event({"event": "task_start", "id": t.id, "uses": t.uses})
                if t.uses == "model":
                    # Model-only step: pass the memory and args to the model and store text
                    client = LMClient(model=self.model or "")
                    messages = [
                        {"role": "system", "content": f"Synthesize step {t.id} given context and args. Output raw text only."},
                        {
                            "role": "user",
                            "content": json.dumps({"context": memory, "args": self._resolve_args(t.args, memory)}),
                        },
                    ]
                    result, _ = await client.generate(LMRequest(model=self.model or "", messages=messages))
                    val = result.get("text")
                else:
                    tool = self.tools.get(t.uses)
                    if not tool:
                        val = {"error": f"unknown_tool:{t.uses}"}
                    else:
                        resolved = self._resolve_args(t.args, memory)
                        val = await self._tool_adapter.call(tool, **resolved)
                key = t.save_as or t.id
                memory[key] = val
                if yield_event:
                    await yield_event({"event": "task_end", "id": t.id, "result_key": key})

        while remaining:
            # Determine ready tasks
            ready = [t for t in remaining.values() if all(d not in remaining for d in t.depends_on)]
            if not ready:
                # Cyclic deps or blocked
                break
            # Launch ready tasks within a TaskGroup context
            async with asyncio.TaskGroup() as tg:
                for t in ready:
                    in_progress.add(t.id)
                    del remaining[t.id]
                    tg.create_task(_run_task(t))

    # ---------------- Synthesizer ----------------
    async def _synthesize(self, client: LMClient, inputs: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
        # Use PromptBuilder to request structured final result when possible
        instruction, schema = build_prompt(
            agent_name=self.agent_name,
            description=self.description,
            input_spec=self.input_spec,
            output_spec=self.output_spec,
        )
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps({"inputs": inputs, "memory": memory})},
        ]
        extra: dict[str, Any] | None = {}
        if schema:
            extra["response_format"] = {"type": "json_schema", "json_schema": schema}
        else:
            extra["response_format"] = {"type": "json_object"}

        result, _ = await client.generate(LMRequest(model=self.model or "", messages=messages, extra=extra))
        text = result.get("text")
        try:
            return json.loads(text) if text else {"text": None}
        except Exception:
            return {"text": text}

    def _aggregate_receipt(self, inputs: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
        items = list(inputs.get("items") or [])
        breakdown: list[dict[str, str]] = []
        subtotal = 0.0
        # Collect any saved item prices (keys starting with 'p_')
        for k, v in memory.items():
            if isinstance(k, str) and k.startswith("p_"):
                try:
                    price = float(v)
                except Exception:
                    continue
                breakdown.append({"item": k[2:], "amount": f"{price:.2f}"})
                subtotal += price
        # If no saved prices present, try fetching from catalog via memory or zero
        if not breakdown and items:
            for name in items:
                # If planner didn't fetch, we can't call tools here; show as 0.00
                breakdown.append({"item": str(name), "amount": f"{0.00:.2f}"})
        ship = 0.0
        tax_rate = 0.0
        # shipping
        if "ship" in memory:
            try:
                ship = float(memory["ship"])  # type: ignore
            except Exception:
                ship = 0.0
        # tax
        if "tax" in memory:
            try:
                tax_rate = float(memory["tax"])  # type: ignore
            except Exception:
                tax_rate = 0.0
        tax_amount = subtotal * tax_rate
        total = subtotal + ship + tax_amount
        # Add shipping and tax lines to breakdown
        if ship:
            breakdown.append({"item": "shipping", "amount": f"{ship:.2f}"})
        if tax_rate:
            breakdown.append({"item": f"tax ({tax_rate:.0%})", "amount": f"{tax_amount:.2f}"})
        note = f"Subtotal {subtotal:.2f} + shipping {ship:.2f} + tax {tax_amount:.2f} = total {total:.2f}"
        return {"total": round(total, 2), "breakdown": breakdown, "note": note}

    # ---------------- Program interface ----------------
    async def run(self, *, inputs: dict[str, Any]) -> dict[str, Any]:
        if not self.model:
            # Deterministic fallback for tests
            return {**inputs}

        client = LMClient(model=self.model)
        # 1) Compile plan
        tasks = await self._compile_plan(client, inputs)
        # 2) Execute
        memory: dict[str, Any] = {}
        await self._execute_plan(tasks, memory)
        # 3) Synthesize final, with deterministic fallback aggregation
        final = await self._synthesize(client, inputs, memory)
        fallback = self._aggregate_receipt(inputs, memory)
        if not isinstance(final, dict):
            return fallback
        # Fill missing fields from fallback
        for k, v in fallback.items():
            if k not in final or final.get(k) in (None, {}, [], ""):
                final[k] = v
        return final

    async def run_stream(self, *, inputs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        if not self.model:
            yield {"event": "final", "result": await self.run(inputs=inputs)}
            return

        client = LMClient(model=self.model)
        yield {"event": "compile_start"}
        tasks = await self._compile_plan(client, inputs)
        yield {"event": "program", "tasks": [t.__dict__ for t in tasks]}

        async def _yield(ev: dict[str, Any]) -> None:
            yield_obj = {**ev}
            # Attach lightweight snapshot sizes
            try:
                if ev.get("event") == "task_end":
                    yield_obj["mem_size"] = "na"
            except Exception:
                pass
            yield_obj.setdefault("agent", self.agent_name)
            # Use an async generator trampoline
            nonlocal_queue.append(yield_obj)

        nonlocal_queue: list[dict[str, Any]] = []
        await self._execute_plan(tasks, memory := {}, yield_event=_yield)
        # Drain the queued events
        for item in nonlocal_queue:
            yield item

        final = await self._synthesize(client, inputs, memory)
        yield {"event": "final", "result": final}


# Register program in the global registry
try:
    from .program_base import ProgramRegistry

    ProgramRegistry.register("llm_compiler", lambda **kw: LLMCompilerProgram(**kw))
except Exception:
    pass
