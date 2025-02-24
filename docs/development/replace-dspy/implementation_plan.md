# Flock Custom Prompt Generation & Optimization System

## Implementation Plan

This implementation plan outlines a strategic approach to building a custom prompt system for Flock, replacing the DSPy dependency and adding powerful optimization capabilities. Each phase builds on the previous one, allowing for incremental development and testing.

### Phase 1: Minimal Viable Prompt Generator (2-3 weeks)

**Goal:** Create a direct replacement for DSPy functionality that works with existing agents.

#### Components to Implement:

1. **Core Prompt Builder**

```python
# src/flock/prompting/builder.py
from typing import Any, Dict, List, Optional
from flock.core.flock_agent import FlockAgent
from flock.prompting.schema_parser import parse_input_schema, parse_output_schema

class PromptBuilder:
    """Base prompt builder that converts FlockAgent definitions to prompt text."""
    
    def build_prompt(self, agent: FlockAgent, inputs: Dict[str, Any]) -> str:
        """Build a prompt from the agent definition and inputs."""
        input_schema = parse_input_schema(agent.input)
        output_schema = parse_output_schema(agent.output)
        tools_text = self._format_tools(agent.tools) if agent.tools else ""
        
        return f"""You are {agent.name}, {agent.description or 'an AI assistant'}.

INPUT SCHEMA:
{self._format_schema(input_schema)}

OUTPUT SCHEMA:
{self._format_schema(output_schema)}

{tools_text}

INPUT VALUES:
{self._format_inputs(inputs)}

Generate output based on the provided input, following the output schema.
"""
    
    def _format_schema(self, schema: Dict[str, Dict[str, str]]) -> str:
        """Format a schema into a readable string."""
        result = []
        for field_name, field_info in schema.items():
            field_type = field_info.get("type", "string")
            description = field_info.get("description", "")
            result.append(f"- {field_name}: {field_type} | {description}")
        return "\n".join(result)
    
    def _format_tools(self, tools: List[callable]) -> str:
        """Format tools into a readable string."""
        if not tools:
            return ""
            
        result = ["TOOLS:"]
        for tool in tools:
            tool_name = getattr(tool, "__name__", str(tool))
            tool_doc = getattr(tool, "__doc__", "No description available.")
            result.append(f"- {tool_name}: {tool_doc}")
        return "\n".join(result)
    
    def _format_inputs(self, inputs: Dict[str, Any]) -> str:
        """Format input values into a readable string."""
        return "\n".join([f"{k}: {v}" for k, v in inputs.items()])
```

2. **Schema Parser**

```python
# src/flock/prompting/schema_parser.py
import re
from typing import Dict, Any, List

def parse_input_schema(input_str: str) -> Dict[str, Dict[str, Any]]:
    """Parse the input schema string into a structured format."""
    return _parse_schema(input_str)

def parse_output_schema(output_str: str) -> Dict[str, Dict[str, Any]]:
    """Parse the output schema string into a structured format."""
    return _parse_schema(output_str)

def _parse_schema(schema_str: str) -> Dict[str, Dict[str, Any]]:
    """Parse a schema string into a structured format."""
    schema = {}
    if not schema_str:
        return schema
        
    fields = [f.strip() for f in schema_str.split(",")]
    for field in fields:
        if not field:
            continue
            
        # Parse field name, type, and description
        parts = field.split("|", 1)
        field_def = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else ""
        
        # Handle type annotations
        if ":" in field_def:
            name, type_hint = field_def.split(":", 1)
            name = name.strip()
            type_hint = type_hint.strip()
        else:
            name = field_def
            type_hint = "str"
            
        schema[name] = {
            "type": type_hint,
            "description": description
        }
        
    return schema
```

3. **Evaluator Integration**

```python
# src/flock/evaluators/prompt_evaluator.py
from typing import Any, Dict, List
from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.prompting.builder import PromptBuilder

class PromptEvaluatorConfig(FlockEvaluatorConfig):
    model: str = "openai/gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096
    log_prompts: bool = False

class PromptEvaluator(FlockEvaluator):
    """Evaluator that uses custom prompt generation."""
    
    config: PromptEvaluatorConfig
    prompt_builder: PromptBuilder
    
    def __init__(self, name: str, config: PromptEvaluatorConfig = None):
        super().__init__(name=name, config=config or PromptEvaluatorConfig())
        self.prompt_builder = PromptBuilder()
    
    async def evaluate(self, agent: FlockAgent, inputs: Dict[str, Any], tools: List[Any]) -> Dict[str, Any]:
        """Evaluate using custom prompt generation."""
        # Generate the prompt
        prompt = self.prompt_builder.build_prompt(agent, inputs)
        
        # Log prompt if configured
        if self.config.log_prompts:
            logger.debug(f"Generated prompt for {agent.name}:\n{prompt}")
        
        # Call LLM service
        from flock.services.llm import get_llm_service
        llm = get_llm_service(self.config.model)
        
        response = await llm.complete(
            prompt=prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        
        # Parse response into structured output
        result = self._parse_output(response, agent.output)
        return result
    
    def _parse_output(self, response: str, output_schema: str) -> Dict[str, Any]:
        """Parse LLM response into structured output based on schema."""
        # Basic implementation: for now, try to parse JSON or key-value pairs
        try:
            import json
            return json.loads(response)
        except:
            # Fallback: try to extract key-value pairs from text
            schema = parse_output_schema(output_schema)
            result = {}
            
            for key in schema:
                pattern = rf"{key}:?\s*(.*?)(?:\n\n|\n[A-Z]|$)"
                match = re.search(pattern, response, re.DOTALL)
                if match:
                    result[key] = match.group(1).strip()
            
            return result
```

#### Implementation Steps:

1. Create the core modules (builder, parser, evaluator)
2. Implement one-to-one replacement for DSPy functionality
3. Add unit tests for each component
4. Create integration test comparing output with DSPy
5. Add feature flag to switch between DSPy and custom implementation

#### Success Criteria:
- All existing tests pass with the new prompt system
- Performance metrics are equivalent to DSPy
- No changes required to existing agent definitions

---

### Phase 2: Template System (2 weeks)

**Goal:** Introduce a flexible template system for different agent types and use cases.

#### Components to Implement:

1. **Template Base Class**

```python
# src/flock/prompting/templates/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from flock.core.flock_agent import FlockAgent

class PromptTemplate(ABC):
    """Base class for prompt templates."""
    
    @abstractmethod
    def render(self, 
               agent: FlockAgent, 
               input_schema: Dict[str, Dict[str, Any]],
               output_schema: Dict[str, Dict[str, Any]],
               tools_text: str,
               input_values: Dict[str, Any],
               examples: Optional[List[Dict[str, Any]]] = None) -> str:
        """Render the template with the provided context."""
        pass
```

2. **Standard Templates**

```python
# src/flock/prompting/templates/standard.py
from typing import Dict, Any, List, Optional
from flock.core.flock_agent import FlockAgent
from flock.prompting.templates.base import PromptTemplate

class StandardTemplate(PromptTemplate):
    """Standard prompt template suitable for most tasks."""
    
    def render(self, 
               agent: FlockAgent, 
               input_schema: Dict[str, Dict[str, Any]],
               output_schema: Dict[str, Dict[str, Any]],
               tools_text: str,
               input_values: Dict[str, Any],
               examples: Optional[List[Dict[str, Any]]] = None) -> str:
        """Render the standard template."""
        examples_text = self._format_examples(examples) if examples else ""
        
        return f"""You are {agent.name}, {agent.description or 'an AI assistant'}.

TASK DESCRIPTION:
You will receive input data and need to generate a structured output.

INPUT SCHEMA:
{self._format_schema(input_schema)}

OUTPUT SCHEMA:
{self._format_schema(output_schema)}

{tools_text}

{examples_text}

INPUT VALUES:
{self._format_input_values(input_values)}

Generate output following the exact output schema.
"""

    def _format_schema(self, schema: Dict[str, Dict[str, Any]]) -> str:
        """Format schema into a readable string."""
        lines = []
        for field, info in schema.items():
            field_type = info.get("type", "string")
            description = info.get("description", "")
            lines.append(f"- {field}: {field_type} | {description}")
        return "\n".join(lines)
    
    def _format_input_values(self, values: Dict[str, Any]) -> str:
        """Format input values into a readable string."""
        return "\n".join([f"{k}: {v}" for k, v in values.items()])
    
    def _format_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Format examples into a readable string."""
        if not examples:
            return ""
            
        result = ["EXAMPLES:"]
        for i, example in enumerate(examples, 1):
            result.append(f"Example {i}:")
            result.append("Input:")
            for k, v in example.get("input", {}).items():
                result.append(f"  {k}: {v}")
            result.append("Output:")
            for k, v in example.get("output", {}).items():
                result.append(f"  {k}: {v}")
            result.append("")
        
        return "\n".join(result)
```

3. **ReAct Template**

```python
# src/flock/prompting/templates/react.py
from typing import Dict, Any, List, Optional
from flock.core.flock_agent import FlockAgent
from flock.prompting.templates.base import PromptTemplate

class ReActTemplate(PromptTemplate):
    """Template for agents that use tools with a ReAct pattern."""
    
    def render(self, 
               agent: FlockAgent, 
               input_schema: Dict[str, Dict[str, Any]],
               output_schema: Dict[str, Dict[str, Any]],
               tools_text: str,
               input_values: Dict[str, Any],
               examples: Optional[List[Dict[str, Any]]] = None) -> str:
        """Render the ReAct template."""
        examples_text = self._format_examples(examples) if examples else ""
        
        return f"""You are {agent.name}, {agent.description or 'an AI assistant'}.

TASK DESCRIPTION:
You will receive input data and need to generate a structured output. You can use tools to help you.

INPUT SCHEMA:
{self._format_schema(input_schema)}

OUTPUT SCHEMA:
{self._format_schema(output_schema)}

TOOLS:
{tools_text}

{examples_text}

To solve this task, follow these steps:
1. Think about what you need to do to generate the required output
2. Use tools when necessary by writing:
   Action: tool_name
   Action Input: {{input for the tool}}
3. After using a tool, you'll receive:
   Observation: {{tool result}}
4. Continue this process until you can produce the final output
5. When ready to provide the final answer, write:
   Final Answer: {{your structured output}}

INPUT VALUES:
{self._format_input_values(input_values)}

Begin your reasoning process now.
"""

    # [other helper methods same as StandardTemplate]
```

4. **Template Registry**

```python
# src/flock/prompting/template_registry.py
from typing import Dict, Type
from flock.prompting.templates.base import PromptTemplate
from flock.prompting.templates.standard import StandardTemplate
from flock.prompting.templates.react import ReActTemplate
from flock.prompting.templates.creative import CreativeTemplate

class TemplateRegistry:
    """Registry for prompt templates."""
    
    def __init__(self):
        self._templates: Dict[str, Type[PromptTemplate]] = {
            "standard": StandardTemplate,
            "react": ReActTemplate,
            "creative": CreativeTemplate,
        }
    
    def get_template(self, template_name: str) -> PromptTemplate:
        """Get a template instance by name."""
        if template_name not in self._templates:
            raise ValueError(f"Template '{template_name}' not found.")
        return self._templates[template_name]()
    
    def register_template(self, name: str, template_class: Type[PromptTemplate]) -> None:
        """Register a new template class."""
        self._templates[name] = template_class
    
    def list_templates(self) -> Dict[str, Type[PromptTemplate]]:
        """List all registered templates."""
        return self._templates.copy()
```

5. **Enhanced Prompt Builder**

```python
# src/flock/prompting/enhanced_builder.py
from typing import Any, Dict, List, Optional
from flock.core.flock_agent import FlockAgent
from flock.prompting.schema_parser import parse_input_schema, parse_output_schema
from flock.prompting.template_registry import TemplateRegistry

class EnhancedPromptBuilder:
    """Enhanced prompt builder that uses templates based on agent characteristics."""
    
    def __init__(self):
        self.template_registry = TemplateRegistry()
    
    def build_prompt(self, 
                    agent: FlockAgent, 
                    inputs: Dict[str, Any],
                    template_name: Optional[str] = None,
                    examples: Optional[List[Dict[str, Any]]] = None) -> str:
        """Build a prompt using the appropriate template."""
        # Parse schemas
        input_schema = parse_input_schema(agent.input)
        output_schema = parse_output_schema(agent.output)
        
        # Format tools
        tools_text = self._format_tools(agent.tools) if agent.tools else ""
        
        # Select template
        if template_name:
            template = self.template_registry.get_template(template_name)
        else:
            template_name = self._select_template(agent)
            template = self.template_registry.get_template(template_name)
        
        # Render template
        return template.render(
            agent=agent,
            input_schema=input_schema,
            output_schema=output_schema,
            tools_text=tools_text,
            input_values=inputs,
            examples=examples
        )
    
    def _select_template(self, agent: FlockAgent) -> str:
        """Select the appropriate template based on agent characteristics."""
        if agent.tools:
            return "react"
        elif getattr(agent, "tags", None) and "creative" in agent.tags:
            return "creative"
        else:
            return "standard"
    
    def _format_tools(self, tools: List[callable]) -> str:
        """Format tools into a readable description."""
        tool_texts = []
        for tool in tools:
            name = getattr(tool, "__name__", str(tool))
            doc = getattr(tool, "__doc__", "No description available")
            signature = self._get_tool_signature(tool)
            tool_texts.append(f"{name}{signature}\n{doc}")
        return "\n\n".join(tool_texts)
    
    def _get_tool_signature(self, tool: callable) -> str:
        """Get the signature of a tool as a string."""
        import inspect
        try:
            sig = inspect.signature(tool)
            params = []
            for name, param in sig.parameters.items():
                if param.annotation != inspect.Parameter.empty:
                    params.append(f"{name}: {param.annotation.__name__}")
                else:
                    params.append(name)
            return f"({', '.join(params)})"
        except:
            return "()"
```

#### Implementation Steps:

1. Create template base class and standard implementations
2. Build template registry for organizing and retrieving templates
3. Enhance prompt builder to use appropriate templates
4. Add unit tests for each template
5. Update evaluator to use enhanced prompt builder

#### Success Criteria:
- Different agent types automatically use the most appropriate template
- Custom templates can be registered and used
- Template rendering correctly handles all edge cases

---

### Phase 3: Instrumentation and Metrics (1-2 weeks)

**Goal:** Add comprehensive instrumentation to track prompt performance and gather data for optimization.

#### Components to Implement:

1. **Prompt Metrics Collector**

```python
# src/flock/prompting/metrics.py
import time
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

@dataclass
class PromptMetrics:
    """Metrics for a single prompt execution."""
    agent_name: str
    template_name: str
    input_token_count: int
    output_token_count: int
    total_token_count: int
    prompt_length: int
    response_length: int
    latency_ms: float
    success: bool
    parsing_success: bool
    timestamp: float = time.time()
    tags: Dict[str, str] = None
    
class PromptMetricsCollector:
    """Collects metrics about prompt usage and performance."""
    
    def __init__(self):
        self._metrics: List[PromptMetrics] = []
    
    def record_prompt_metrics(self, metrics: PromptMetrics) -> None:
        """Record metrics for a prompt execution."""
        self._metrics.append(metrics)
    
    def get_metrics(self, 
                   agent_name: Optional[str] = None, 
                   template_name: Optional[str] = None,
                   tag_filter: Optional[Dict[str, str]] = None) -> List[PromptMetrics]:
        """Get recorded metrics with optional filtering."""
        filtered = self._metrics
        
        if agent_name:
            filtered = [m for m in filtered if m.agent_name == agent_name]
        
        if template_name:
            filtered = [m for m in filtered if m.template_name == template_name]
        
        if tag_filter:
            filtered = [
                m for m in filtered 
                if m.tags and all(m.tags.get(k) == v for k, v in tag_filter.items())
            ]
            
        return filtered
    
    def get_summary_stats(self,
                         agent_name: Optional[str] = None, 
                         template_name: Optional[str] = None) -> Dict[str, Any]:
        """Get summary statistics for the collected metrics."""
        metrics = self.get_metrics(agent_name, template_name)
        
        if not metrics:
            return {}
            
        input_tokens = [m.input_token_count for m in metrics]
        output_tokens = [m.output_token_count for m in metrics]
        total_tokens = [m.total_token_count for m in metrics]
        latencies = [m.latency_ms for m in metrics]
        success_rate = sum(1 for m in metrics if m.success) / len(metrics)
        parsing_success_rate = sum(1 for m in metrics if m.parsing_success) / len(metrics)
        
        return {
            "count": len(metrics),
            "input_tokens": {
                "mean": sum(input_tokens) / len(input_tokens),
                "min": min(input_tokens),
                "max": max(input_tokens),
            },
            "output_tokens": {
                "mean": sum(output_tokens) / len(output_tokens),
                "min": min(output_tokens),
                "max": max(output_tokens),
            },
            "total_tokens": {
                "mean": sum(total_tokens) / len(total_tokens),
                "min": min(total_tokens),
                "max": max(total_tokens),
            },
            "latency_ms": {
                "mean": sum(latencies) / len(latencies),
                "min": min(latencies),
                "max": max(latencies),
            },
            "success_rate": success_rate,
            "parsing_success_rate": parsing_success_rate,
        }
```

2. **Instrumented Evaluator**

```python
# src/flock/evaluators/instrumented_prompt_evaluator.py
import time
from typing import Any, Dict, List, Optional
from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.prompting.enhanced_builder import EnhancedPromptBuilder
from flock.prompting.metrics import PromptMetrics, PromptMetricsCollector

class InstrumentedPromptEvaluatorConfig(FlockEvaluatorConfig):
    model: str = "openai/gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096
    log_prompts: bool = False
    collect_metrics: bool = True
    template_name: Optional[str] = None

class InstrumentedPromptEvaluator(FlockEvaluator):
    """Evaluator that uses custom prompt generation with instrumentation."""
    
    config: InstrumentedPromptEvaluatorConfig
    prompt_builder: EnhancedPromptBuilder
    metrics_collector: PromptMetricsCollector
    
    def __init__(self, 
                name: str, 
                config: InstrumentedPromptEvaluatorConfig = None,
                metrics_collector: Optional[PromptMetricsCollector] = None):
        super().__init__(name=name, config=config or InstrumentedPromptEvaluatorConfig())
        self.prompt_builder = EnhancedPromptBuilder()
        self.metrics_collector = metrics_collector or PromptMetricsCollector()
    
    async def evaluate(self, agent: FlockAgent, inputs: Dict[str, Any], tools: List[Any]) -> Dict[str, Any]:
        """Evaluate using custom prompt generation with metrics collection."""
        start_time = time.time()
        parsing_success = True
        
        try:
            # Generate the prompt
            template_name = self.config.template_name or self._select_template(agent)
            prompt = self.prompt_builder.build_prompt(
                agent=agent, 
                inputs=inputs,
                template_name=template_name
            )
            
            # Log prompt if configured
            if self.config.log_prompts:
                logger.debug(f"Generated prompt for {agent.name}:\n{prompt}")
            
            # Get token counts
            input_token_count = self._count_tokens(prompt)
            
            # Call LLM service
            from flock.services.llm import get_llm_service
            llm = get_llm_service(self.config.model)
            
            response = await llm.complete(
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            # Get output token count
            output_token_count = self._count_tokens(response)
            
            # Parse response into structured output
            try:
                result = self._parse_output(response, agent.output)
            except Exception:
                parsing_success = False
                # Fallback to returning raw response
                result = {"raw_response": response}
            
            # Record metrics
            if self.config.collect_metrics:
                elapsed_ms = (time.time() - start_time) * 1000
                metrics = PromptMetrics(
                    agent_name=agent.name,
                    template_name=template_name,
                    input_token_count=input_token_count,
                    output_token_count=output_token_count,
                    total_token_count=input_token_count + output_token_count,
                    prompt_length=len(prompt),
                    response_length=len(response),
                    latency_ms=elapsed_ms,
                    success=True,
                    parsing_success=parsing_success,
                    tags={"model": self.config.model}
                )
                self.metrics_collector.record_prompt_metrics(metrics)
            
            return result
            
        except Exception as e:
            # Record failure metrics
            if self.config.collect_metrics:
                elapsed_ms = (time.time() - start_time) * 1000
                metrics = PromptMetrics(
                    agent_name=agent.name,
                    template_name=self.config.template_name or "unknown",
                    input_token_count=0,
                    output_token_count=0,
                    total_token_count=0,
                    prompt_length=0,
                    response_length=0,
                    latency_ms=elapsed_ms,
                    success=False,
                    parsing_success=False,
                    tags={"error": str(e), "model": self.config.model}
                )
                self.metrics_collector.record_prompt_metrics(metrics)
            
            raise
    
    def _select_template(self, agent: FlockAgent) -> str:
        """Select the appropriate template for this agent."""
        if agent.tools:
            return "react"
        elif getattr(agent, "tags", None) and "creative" in agent.tags:
            return "creative"
        else:
            return "standard"
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        try:
            import tiktoken
            encoder = tiktoken.encoding_for_model(
                self.config.model.replace("openai/", "")
            )
            return len(encoder.encode(text))
        except:
            # Fallback: estimate 1 token per 4 characters
            return len(text) // 4
    
    def _parse_output(self, response: str, output_schema: str) -> Dict[str, Any]:
        """Parse LLM response into structured output based on schema."""
        # Implementation same as previous version
```

3. **Metrics Export and Visualization**

```python
# src/flock/prompting/metrics_export.py
import json
import os
from datetime import datetime
from typing import List, Optional
from flock.prompting.metrics import PromptMetrics, PromptMetricsCollector

class MetricsExporter:
    """Export prompt metrics to various formats."""
    
    def export_to_json(self, 
                      metrics_collector: PromptMetricsCollector,
                      output_path: str,
                      agent_name: Optional[str] = None) -> None:
        """Export metrics to a JSON file."""
        metrics = metrics_collector.get_metrics(agent_name=agent_name)
        
        # Convert metrics to dicts
        metrics_dicts = []
        for metric in metrics:
            metric_dict = {
                "agent_name": metric.agent_name,
                "template_name": metric.template_name,
                "input_token_count": metric.input_token_count,
                "output_token_count": metric.output_token_count,
                "total_token_count": metric.total_token_count,
                "prompt_length": metric.prompt_length,
                "response_length": metric.response_length,
                "latency_ms": metric.latency_ms,
                "success": metric.success,
                "parsing_success": metric.parsing_success,
                "timestamp": metric.timestamp,
                "tags": metric.tags or {}
            }
            metrics_dicts.append(metric_dict)
        
        # Write to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(metrics_dicts, f, indent=2)
    
    def export_to_csv(self,
                     metrics_collector: PromptMetricsCollector,
                     output_path: str,
                     agent_name: Optional[str] = None) -> None:
        """Export metrics to a CSV file."""
        import csv
        
        metrics = metrics_collector.get_metrics(agent_name=agent_name)
        
        # Write to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                "agent_name",
                "template_name",
                "input_token_count",
                "output_token_count",
                "total_token_count",
                "prompt_length",
                "response_length",
                "latency_ms",
                "success",
                "parsing_success",
                "timestamp",
                "tags"
            ])
            
            # Write rows
            for metric in metrics:
                writer.writerow([
                    metric.agent_name,
                    metric.template_name,
                    metric.input_token_count,
                    metric.output_token_count,
                    metric.total_token_count,
                    metric.prompt_length,
                    metric.response_length,
                    metric.latency_ms,
                    metric.success,
                    metric.parsing_success,
                    metric.timestamp,
                    json.dumps(metric.tags or {})
                ])
```

#### Implementation Steps:

1. Build metrics collection classes
2. Enhance evaluator with instrumentation
3. Implement metrics export and visualization
4. Add unit tests for metrics collection
5. Update evaluator factory to produce instrumented evaluators

#### Success Criteria:
- Complete metrics collection for all prompt executions
- Proper token counting and latency tracking
- Ability to export metrics for analysis
- Minimal performance overhead

---

### Phase 4: Basic Optimization Strategies (2 weeks)

**Goal:** Implement foundational optimization strategies for prompt efficiency and effectiveness.

#### Components to Implement:

1. **Token Budget Manager**

```python
# src/flock/prompting/optimization/token_budget.py
from typing import Dict, Any, List, Optional
import json

class TokenBudgetManager:
    """Manages token budgets for prompts to optimize for model context limits."""
    
    def __init__(self, model_name: str, max_tokens: int):
        self.model_name = model_name
        self.max_budget = max_tokens
        self.safety_margin = 50  # tokens reserved for unexpected variations
        
    def allocate_budget(self, 
                       sections: Dict[str, str], 
                       priorities: Dict[str, int]) -> Dict[str, str]:
        """Allocate token budget to different prompt sections based on priorities."""
        # Count tokens for each section
        section_tokens = {
            key: self._count_tokens(content)
            for key, content in sections.items()
        }
        
        total_tokens = sum(section_tokens.values())
        
        # If we're under budget, no need to optimize
        if total_tokens + self.safety_margin <= self.max_budget:
            return sections
        
        # We need to reduce token count
        # Sort sections by priority (lower priority gets trimmed first)
        sorted_sections = sorted(
            sections.keys(),
            key=lambda k: priorities.get(k, 5)  # Default to medium priority
        )
        
        optimized_sections = sections.copy()
        
        # Trim sections starting from lowest priority
        for section_key in sorted_sections:
            if sum(self._count_tokens(optimized_sections[k]) for k in optimized_sections) <= self.max_budget:
                break
                
            # Apply optimization strategy based on section type
            if section_key == "examples":
                optimized_sections[section_key] = self._optimize_examples(
                    optimized_sections[section_key]
                )
            elif section_key == "tools":
                optimized_sections[section_key] = self._optimize_tools(
                    optimized_sections[section_key]
                )
            elif section_key == "context":
                optimized_sections[section_key] = self._optimize_context(
                    optimized_sections[section_key]
                )
            else:
                # Generic optimization: truncate with a notice
                current_tokens = self._count_tokens(optimized_sections[section_key])
                target_tokens = current_tokens // 2  # Cut by half
                optimized_sections[section_key] = self._truncate_to_token_count(
                    optimized_sections[section_key],
                    target_tokens
                )
        
        return optimized_sections
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        try:
            import tiktoken
            model = self.model_name.replace("openai/", "")
            encoder = tiktoken.encoding_for_model(model)
            return len(encoder.encode(text))
        except:
            # Fallback: estimate 1 token per 4 characters
            return len(text) // 4
    
    def _optimize_examples(self, examples_text: str) -> str:
        """Optimize examples section by removing or truncating examples."""
        # If empty, nothing to optimize
        if not examples_text.strip():
            return examples_text
            
        # Split into individual examples
        import re
        examples = re.split(r"Example \d+:", examples_text)
        examples = [ex for ex in examples if ex.strip()]
        
        if not examples:
            return examples_text
            
        # If we have multiple examples, keep only the first one
        if len(examples) > 1:
            return "Example 1:" + examples[0]
            
        # If we only have one example, return it as is
        return examples_text
    
    def _optimize_tools(self, tools_text: str) -> str:
        """Optimize tools section by keeping only essential information."""
        # If empty, nothing to optimize
        if not tools_text.strip():
            return tools_text
            
        # Split into individual tools
        tools = tools_text.split("\n\n")
        
        optimized_tools = []
        for tool in tools:
            # Keep only the first line (name and signature) and a truncated description
            lines = tool.split("\n")
            if not lines:
                continue
                
            name_line = lines[0]
            
            if len(lines) > 1:
                # Take only the first sentence of the description
                desc = lines[1].split(". ")[0] + "."
                optimized_tools.append(f"{name_line}\n{desc}")
            else:
                optimized_tools.append(name_line)
        
        return "\n\n".join(optimized_tools)
    
    def _optimize_context(self, context_text: str) -> str:
        """Optimize context by summarizing or truncating."""
        # If the context is JSON, we might be able to simplify it
        try:
            data = json.loads(context_text)
            # For JSON, keep only essential fields
            if isinstance(data, dict):
                essential_keys = self._get_essential_keys(data)
                simplified_data = {k: data[k] for k in essential_keys if k in data}
                return json.dumps(simplified_data, indent=2)
            return context_text
        except:
            # Not JSON, truncate by preserving the beginning and end
            return self._truncate_middle(context_text)
    
    def _get_essential_keys(self, data: Dict[str, Any]) -> List[str]:
        """Determine which keys in a dictionary are likely to be essential."""
        # This is a heuristic based on common field names
        important_key_patterns = [
            "id", "name", "title", "description", "summary",
            "key", "main", "primary", "essential", "critical"
        ]
        
        # Keep keys that contain any of the important patterns
        return [
            key for key in data.keys()
            if any(pattern in key.lower() for pattern in important_key_patterns)
        ]
    
    def _truncate_to_token_count(self, text: str, target_tokens: int) -> str:
        """Truncate text to approximately the target token count."""
        current_tokens = self._count_tokens(text)
        
        if current_tokens <= target_tokens:
            return text
            
        # Estimate characters per token (usually around 4)
        chars_per_token = len(text) / current_tokens
        
        # Estimate target character count
        target_chars = int(target_tokens * chars_per_token)
        
        # Cut to target length
        if target_chars <= 0:
            return ""
            
        truncated = text[:target_chars]
        
        # Add notice of truncation
        truncation_notice = f"\n[Content truncated to fit token budget. Originally {current_tokens} tokens.]"
        
        return truncated + truncation_notice
    
    def _truncate_middle(self, text: str, keep_ratio: float = 0.3) -> str:
        """Truncate the middle portion of text, keeping the beginning and end."""
        tokens = self._count_tokens(text)
        
        if tokens <= self.max_budget:
            return text
            
        # Determine how many tokens to keep from start and end
        keep_tokens = int(self.max_budget * keep_ratio)
        
        # Estimate characters for the kept portions
        chars_per_token = len(text) / tokens
        keep_chars_start = int(keep_tokens * chars_per_token)
        keep_chars_end = int(keep_tokens * chars_per_token)
        
        start_text = text[:keep_chars_start]
        end_text = text[-keep_chars_end:]
        
        return f"{start_text}\n[...content truncated to fit token budget...]\n{end_text}"
```

2. **Example Selector**

```python
# src/flock/prompting/optimization/example_selector.py
from typing import Dict, Any, List
import random

class ExampleSelector:
    """Selects the most relevant examples for a given input."""
    
    def __init__(self, examples_store_path: str = None):
        self.examples = {}
        if examples_store_path:
            self._load_examples(examples_store_path)
    
    def _load_examples(self, path: str) -> None:
        """Load examples from a JSON file."""
        import json
        try:
            with open(path, "r") as f:
                self.examples = json.load(f)
        except Exception as e:
            print(f"Error loading examples: {e}")
    
    def select_examples(self, 
                      agent_name: str, 
                      inputs: Dict[str, Any], 
                      count: int = 2) -> List[Dict[str, Any]]:
        """Select the most relevant examples for the given input."""
        # If we don't have examples for this agent, return empty list
        if agent_name not in self.examples:
            return []
            
        agent_examples = self.examples.get(agent_name, [])
        
        # If we have fewer examples than requested, return all
        if len(agent_examples) <= count:
            return agent_examples
            
        # For now, use a simple random selection
        # In future versions, we'll add semantic similarity matching
        return random.sample(agent_examples, count)
    
    def add_example(self, 
                   agent_name: str, 
                   input_data: Dict[str, Any], 
                   output_data: Dict[str, Any],
                   metadata: Dict[str, Any] = None) -> None:
        """Add a new example to the store."""
        if agent_name not in self.examples:
            self.examples[agent_name] = []
            
        self.examples[agent_name].append({
            "input": input_data,
            "output": output_data,
            "metadata": metadata or {}
        })
    
    def save_examples(self, path: str) -> None:
        """Save examples to a JSON file."""
        import json
        import os
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.examples, f, indent=2)
```

3. **Template Selector**

```python
# src/flock/prompting/optimization/template_selector.py
from typing import Dict, Any, List, Optional, Tuple
from flock.core.flock_agent import FlockAgent

class TemplateSelector:
    """Selects the most appropriate template for a given agent and input."""
    
    def __init__(self, 
                performance_data: Optional[Dict[str, Dict[str, float]]] = None,
                heuristic_weight: float = 0.7):
        self.performance_data = performance_data or {}
        self.heuristic_weight = heuristic_weight
    
    def select_template(self, 
                       agent: FlockAgent, 
                       inputs: Dict[str, Any]) -> str:
        """Select the most appropriate template based on agent and input characteristics."""
        # Check all available templates
        template_scores = {}
        
        # Rule-based scoring
        for template_name in ["standard", "react", "creative"]:
            template_scores[template_name] = self._score_template_heuristic(
                template_name, agent, inputs
            )
        
        # Performance-based scoring
        if agent.name in self.performance_data:
            for template_name, score in self.performance_data[agent.name].items():
                if template_name in template_scores:
                    # Combine heuristic and performance scores
                    heuristic_score = template_scores[template_name]
                    template_scores[template_name] = (
                        heuristic_score * self.heuristic_weight + 
                        score * (1 - self.heuristic_weight)
                    )
        
        # Select the template with the highest score
        best_template = max(template_scores.items(), key=lambda x: x[1])[0]
        return best_template
    
    def _score_template_heuristic(self, 
                                template_name: str, 
                                agent: FlockAgent, 
                                inputs: Dict[str, Any]) -> float:
        """Score a template based on heuristic rules."""
        score = 0.5  # Base score
        
        # Check agent tools
        if agent.tools:
            if template_name == "react":
                score += 0.4
            else:
                score -= 0.2
        
        # Check agent tags
        tags = getattr(agent, "tags", [])
        if "creative" in tags:
            if template_name == "creative":
                score += 0.3
            else:
                score -= 0.1
        
        # Check output structure
        if hasattr(agent, "output") and ":" in agent.output:
            output_parts = agent.output.split(",")
            if len(output_parts) > 3:  # Complex output
                if template_name == "standard":
                    score += 0.2
        
        # Clamp score to [0, 1]
        return max(0.0, min(1.0, score))
    
    def update_performance_data(self, 
                              agent_name: str, 
                              template_name: str, 
                              success_rate: float) -> None:
        """Update performance data for an agent and template combination."""
        if agent_name not in self.performance_data:
            self.performance_data[agent_name] = {}
            
        self.performance_data[agent_name][template_name] = success_rate
```

4. **Optimized Prompt Builder**

```python
# src/flock/prompting/optimization/optimized_builder.py
from typing import Dict, Any, List, Optional
from flock.core.flock_agent import FlockAgent
from flock.prompting.enhanced_builder import EnhancedPromptBuilder
from flock.prompting.optimization.token_budget import TokenBudgetManager
from flock.prompting.optimization.example_selector import ExampleSelector
from flock.prompting.optimization.template_selector import TemplateSelector

class OptimizedPromptBuilder(EnhancedPromptBuilder):
    """Prompt builder with optimization strategies."""
    
    def __init__(self, 
                model: str = "openai/gpt-4o",
                max_tokens: int = 8192,
                examples_store_path: Optional[str] = None,
                performance_data: Optional[Dict[str, Dict[str, float]]] = None):
        super().__init__()
        self.token_budget_manager = TokenBudgetManager(model, max_tokens)
        self.example_selector = ExampleSelector(examples_store_path)
        self.template_selector = TemplateSelector(performance_data)
    
    def build_prompt(self, 
                    agent: FlockAgent, 
                    inputs: Dict[str, Any],
                    template_name: Optional[str] = None,
                    examples: Optional[List[Dict[str, Any]]] = None) -> str:
        """Build an optimized prompt."""
        # Select template if not specified
        if not template_name:
            template_name = self.template_selector.select_template(agent, inputs)
        
        # Select examples if not provided
        if examples is None:
            examples = self.example_selector.select_examples(agent.name, inputs)
        
        # Parse schemas
        input_schema = self._parse_input_schema(agent.input)
        output_schema = self._parse_output_schema(agent.output)
        
        # Format tools
        tools_text = self._format_tools(agent.tools) if agent.tools else ""
        
        # Get template
        template = self.template_registry.get_template(template_name)
        
        # Generate initial sections
        sections = {
            "intro": f"You are {agent.name}, {agent.description or 'an AI assistant'}.",
            "task": "You will receive input data and need to generate a structured output.",
            "input_schema": self._format_schema(input_schema),
            "output_schema": self._format_schema(output_schema),
            "tools": tools_text,
            "examples": self._format_examples(examples) if examples else "",
            "input_values": self._format_input_values(inputs),
            "outro": "Generate output following the exact output schema."
        }
        
        # Define priorities for sections (higher = more important)
        priorities = {
            "intro": 5,
            "task": 7,
            "input_schema": 8,
            "output_schema": 9,  # Highest priority
            "tools": 6,
            "examples": 3,  # Lower priority
            "input_values": 10,  # Highest priority
            "outro": 4
        }
        
        # Optimize sections for token budget
        optimized_sections = self.token_budget_manager.allocate_budget(sections, priorities)
        
        # Assemble final prompt
        prompt_parts = [
            optimized_sections["intro"],
            "\nTASK DESCRIPTION:",
            optimized_sections["task"],
            "\nINPUT SCHEMA:",
            optimized_sections["input_schema"],
            "\nOUTPUT SCHEMA:",
            optimized_sections["output_schema"],
        ]
        
        if optimized_sections["tools"]:
            prompt_parts.extend(["\nTOOLS:", optimized_sections["tools"]])
            
        if optimized_sections["examples"]:
            prompt_parts.extend(["\nEXAMPLES:", optimized_sections["examples"]])
            
        prompt_parts.extend([
            "\nINPUT VALUES:",
            optimized_sections["input_values"],
            "\n" + optimized_sections["outro"]
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_input_schema(self, input_str: str) -> Dict[str, Dict[str, Any]]:
        """Parse the input schema string into a structured format."""
        from flock.prompting.schema_parser import parse_input_schema
        return parse_input_schema(input_str)
    
    def _parse_output_schema(self, output_str: str) -> Dict[str, Dict[str, Any]]:
        """Parse the output schema string into a structured format."""
        from flock.prompting.schema_parser import parse_output_schema
        return parse_output_schema(output_str)
    
    def _format_schema(self, schema: Dict[str, Dict[str, Any]]) -> str:
        """Format a schema into a readable string."""
        result = []
        for field_name, field_info in schema.items():
            field_type = field_info.get("type", "string")
            description = field_info.get("description", "")
            result.append(f"- {field_name}: {field_type} | {description}")
        return "\n".join(result)
    
    def _format_examples(self, examples: List[Dict[str, Any]]) -> str:
        """Format examples into a readable string."""
        if not examples:
            return ""
            
        result = []
        for i, example in enumerate(examples, 1):
            result.append(f"Example {i}:")
            result.append("Input:")
            for k, v in example.get("input", {}).items():
                result.append(f"  {k}: {v}")
            result.append("Output:")
            for k, v in example.get("output", {}).items():
                result.append(f"  {k}: {v}")
            result.append("")
        
        return "\n".join(result)
    
    def _format_input_values(self, inputs: Dict[str, Any]) -> str:
        """Format input values into a readable string."""
        return "\n".join([f"{k}: {v}" for k, v in inputs.items()])
```

5. **Optimized Evaluator**

```python
# src/flock/evaluators/optimized_prompt_evaluator.py
import time
from typing import Any, Dict, List, Optional
from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.prompting.optimization.optimized_builder import OptimizedPromptBuilder
from flock.prompting.metrics import PromptMetrics, PromptMetricsCollector

class OptimizedPromptEvaluatorConfig(FlockEvaluatorConfig):
    model: str = "openai/gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 4096
    log_prompts: bool = False
    collect_metrics: bool = True
    template_name: Optional[str] = None
    examples_store_path: Optional[str] = None
    performance_data_path: Optional[str] = None

class OptimizedPromptEvaluator(FlockEvaluator):
    """Evaluator with optimized prompt generation."""
    
    config: OptimizedPromptEvaluatorConfig
    prompt_builder: OptimizedPromptBuilder
    metrics_collector: PromptMetricsCollector
    
    def __init__(self, 
                name: str, 
                config: OptimizedPromptEvaluatorConfig = None,
                metrics_collector: Optional[PromptMetricsCollector] = None):
        super().__init__(name=name, config=config or OptimizedPromptEvaluatorConfig())
        
        # Load performance data if available
        performance_data = None
        if self.config.performance_data_path:
            try:
                import json
                with open(self.config.performance_data_path, "r") as f:
                    performance_data = json.load(f)
            except:
                pass
        
        self.prompt_builder = OptimizedPromptBuilder(
            model=self.config.model,
            max_tokens=self.config.max_tokens - self.config.max_tokens // 4,  # Leave room for response
            examples_store_path=self.config.examples_store_path,
            performance_data=performance_data
        )
        self.metrics_collector = metrics_collector or PromptMetricsCollector()
    
    async def evaluate(self, agent: FlockAgent, inputs: Dict[str, Any], tools: List[Any]) -> Dict[str, Any]:
        """Evaluate using optimized prompt generation."""
        start_time = time.time()
        parsing_success = True
        template_name = self.config.template_name
        
        try:
            # Generate the prompt
            prompt = self.prompt_builder.build_prompt(
                agent=agent, 
                inputs=inputs,
                template_name=template_name
            )
            
            # Log prompt if configured
            if self.config.log_prompts:
                logger.debug(f"Generated prompt for {agent.name}:\n{prompt}")
            
            # Get token counts
            input_token_count = self._count_tokens(prompt)
            
            # Call LLM service
            from flock.services.llm import get_llm_service
            llm = get_llm_service(self.config.model)
            
            response = await llm.complete(
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            # Get output token count
            output_token_count = self._count_tokens(response)
            
            # Parse response into structured output
            try:
                result = self._parse_output(response, agent.output)
            except Exception:
                parsing_success = False
                # Fallback to returning raw response
                result = {"raw_response": response}
            
            # Record metrics
            if self.config.collect_metrics:
                elapsed_ms = (time.time() - start_time) * 1000
                template_name = template_name or self.prompt_builder.template_selector.select_template(agent, inputs)
                metrics = PromptMetrics(
                    agent_name=agent.name,
                    template_name=template_name,
                    input_token_count=input_token_count,
                    output_token_count=output_token_count,
                    total_token_count=input_token_count + output_token_count,
                    prompt_length=len(prompt),
                    response_length=len(response),
                    latency_ms=elapsed_ms,
                    success=True,
                    parsing_success=parsing_success,
                    tags={"model": self.config.model}
                )
                self.metrics_collector.record_prompt_metrics(metrics)
                
                # Update performance data for this template
                if parsing_success:
                    self.prompt_builder.template_selector.update_performance_data(
                        agent.name, template_name, 1.0
                    )
                else:
                    self.prompt_builder.template_selector.update_performance_data(
                        agent.name, template_name, 0.0
                    )
                
                # If this was a successful example, store it
                if parsing_success:
                    self.prompt_builder.example_selector.add_example(
                        agent.name,
                        inputs,
                        result,
                        {"timestamp": time.time()}
                    )
            
            return result
            
        except Exception as e:
            # Record failure metrics
            if self.config.collect_metrics:
                elapsed_ms = (time.time() - start_time) * 1000
                metrics = PromptMetrics(
                    agent_name=agent.name,
                    template_name=template_name or "unknown",
                    input_token_count=0,
                    output_token_count=0,
                    total_token_count=0,
                    prompt_length=0,
                    response_length=0,
                    latency_ms=elapsed_ms,
                    success=False,
                    parsing_success=False,
                    tags={"error": str(e), "model": self.config.model}
                )
                self.metrics_collector.record_prompt_metrics(metrics)
            
            raise
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        try:
            import tiktoken
            encoder = tiktoken.encoding_for_model(
                self.config.model.replace("openai/", "")
            )
            return len(encoder.encode(text))
        except:
            # Fallback: estimate 1 token per 4 characters
            return len(text) // 4
    
    def _parse_output(self, response: str, output_schema: str) -> Dict[str, Any]:
        """Parse LLM response into structured output based on schema."""
        # Implementation same as previous version
```

#### Implementation Steps:

1. Build the token budget manager
2. Implement example selection and template selection strategies
3. Create optimized prompt builder
4. Develop optimized evaluator
5. Add unit tests for optimization strategies
6. Update evaluator factory to support optimization

#### Success Criteria:
- Token usage reduction of at least 20% on average
- Improved response parsing success rate
- Automatic template selection based on agent characteristics
- Dynamic example selection based on relevance

---

### Phase 5: A/B Testing Framework (1-2 weeks)

**Goal:** Create a framework for systematically testing and comparing different prompt strategies.

#### Components to Implement:

1. **Test Case Definition**

```python
# src/flock/prompting/testing/test_case.py
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

@dataclass
class TestCase:
    """A test case for evaluating prompt strategies."""
    
    inputs: Dict[str, Any]
    expected_outputs: Dict[str, Any]
    name: str = ""
    tags: List[str] = field(default_factory=list)
    
    def validate_output(self, actual_output: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the actual output against expected output.
        
        Returns a dict with validation results.
        """
        results = {
            "success": True,
            "field_results": {},
            "missing_fields": [],
            "extra_fields": []
        }
        
        # Check for missing fields
        for key in self.expected_outputs:
            if key not in actual_output:
                results["success"] = False
                results["missing_fields"].append(key)
        
        # Check for unexpected fields
        for key in actual_output:
            if key not in self.expected_outputs:
                results["extra_fields"].append(key)
        
        # Validate present fields
        for key, expected in self.expected_outputs.items():
            if key not in actual_output:
                continue
                
            actual = actual_output[key]
            
            # Simple equality check by default
            if expected == actual:
                results["field_results"][key] = {"success": True, "score": 1.0}
            else:
                results["field_results"][key] = {"success": False, "score": 0.0}
                results["success"] = False
        
        return results

@dataclass
class TestSuite:
    """A collection of test cases for A/B testing."""
    
    name: str
    test_cases: List[TestCase]
    description: str = ""
    validator: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = None
    
    def run(self, 
           evaluator_func: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """Run all test cases using the provided evaluator function.
        
        Returns overall results and per-test-case results.
        """
        results = {
            "suite_name": self.name,
            "total_cases": len(self.test_cases),
            "success_count": 0,
            "success_rate": 0.0,
            "case_results": {}
        }
        
        # Run each test case
        for case in self.test_cases:
            try:
                actual_output = evaluator_func(case.inputs)
                
                # Use custom validator if provided
                if self.validator:
                    validation_result = self.validator(actual_output, case.expected_outputs)
                else:
                    validation_result = case.validate_output(actual_output)
                
                results["case_results"][case.name or str(id(case))] = {
                    "success": validation_result["success"],
                    "details": validation_result
                }
                
                if validation_result["success"]:
                    results["success_count"] += 1
                    
            except Exception as e:
                results["case_results"][case.name or str(id(case))] = {
                    "success": False,
                    "error": str(e)
                }
        
        # Calculate overall success rate
        results["success_rate"] = results["success_count"] / len(self.test_cases)
        
        return results
```

2. **A/B Test Runner**

```python
# src/flock/prompting/testing/ab_tester.py
from dataclasses import dataclass
from typing import Dict, Any, List, Callable, Optional
import time
import json
import os
from flock.prompting.testing.test_case import TestSuite

@dataclass
class PromptVariant:
    """A variant of a prompt strategy to test."""
    
    name: str
    builder_func: Callable[[Dict[str, Any]], str]
    description: str = ""
    parameters: Dict[str, Any] = None

@dataclass
class ABTestResult:
    """Results of an A/B test run."""
    
    variant_name: str
    success_rate: float
    avg_latency_ms: float
    avg_token_count: int
    case_results: Dict[str, Any]
    timestamp: float = time.time()

class ABTestRunner:
    """Runs A/B tests on different prompt strategies."""
    
    def __init__(self, llm_client, results_dir: str = "results"):
        self.llm_client = llm_client
        self.results_dir = results_dir
        os.makedirs(results_dir, exist_ok=True)
    
    async def run_test(self, 
                    test_suite: TestSuite,
                    variants: List[PromptVariant]) -> Dict[str, ABTestResult]:
        """Run A/B tests on the provided variants using the test suite."""
        results = {}
        
        for variant in variants:
            print(f"Testing variant: {variant.name}")
            # Create evaluator function for this variant
            async def evaluator_func(inputs: Dict[str, Any]) -> Dict[str, Any]:
                prompt = variant.builder_func(inputs)
                start_time = time.time()
                response = await self.llm_client.complete(prompt)
                elapsed_ms = (time.time() - start_time) * 1000
                
                # Parse the response (simplified version, replace with your actual parser)
                parsed_response = self._parse_response(response)
                
                # Store metadata for analysis
                parsed_response["_metadata"] = {
                    "latency_ms": elapsed_ms,
                    "prompt_tokens": self._count_tokens(prompt),
                    "response_tokens": self._count_tokens(response),
                    "prompt": prompt,
                    "raw_response": response
                }
                
                return parsed_response
            
            # Run the test suite
            suite_results = await test_suite.run(evaluator_func)
            
            # Calculate metrics
            total_latency = 0
            total_tokens = 0
            count = 0
            
            for case_name, case_result in suite_results["case_results"].items():
                if "_metadata" in case_result:
                    metadata = case_result["_metadata"]
                    total_latency += metadata.get("latency_ms", 0)
                    total_tokens += metadata.get("prompt_tokens", 0) + metadata.get("response_tokens", 0)
                    count += 1
            
            avg_latency = total_latency / count if count > 0 else 0
            avg_tokens = total_tokens / count if count > 0 else 0
            
            # Create test result
            results[variant.name] = ABTestResult(
                variant_name=variant.name,
                success_rate=suite_results["success_rate"],
                avg_latency_ms=avg_latency,
                avg_token_count=avg_tokens,
                case_results=suite_results["case_results"]
            )
            
            # Save results
            self._save_results(test_suite.name, variant.name, results[variant.name])
        
        return results
    
    def compare_results(self, results: Dict[str, ABTestResult]) -> Dict[str, Any]:
        """Compare results of different variants."""
        if not results:
            return {}
            
        # Find the best variant for each metric
        best_success = max(results.values(), key=lambda r: r.success_rate)
        best_latency = min(results.values(), key=lambda r: r.avg_latency_ms)
        best_token_efficiency = min(results.values(), key=lambda r: r.avg_token_count)
        
        # Calculate improvement percentages
        baseline = next(iter(results.values()))  # Use first variant as baseline
        
        comparisons = {}
        for name, result in results.items():
            if name == baseline.variant_name:
                continue
                
            comparisons[name] = {
                "success_rate_change": (result.success_rate - baseline.success_rate) / baseline.success_rate * 100,
                "latency_change": (result.avg_latency_ms - baseline.avg_latency_ms) / baseline.avg_latency_ms * 100,
                "token_count_change": (result.avg_token_count - baseline.avg_token_count) / baseline.avg_token_count * 100
            }
        
        return {
            "best_variants": {
                "success_rate": best_success.variant_name,
                "latency": best_latency.variant_name,
                "token_efficiency": best_token_efficiency.variant_name
            },
            "baseline": baseline.variant_name,
            "comparisons": comparisons
        }
    
    def _save_results(self, 
                     test_suite_name: str, 
                     variant_name: str, 
                     result: ABTestResult) -> None:
        """Save test results to a file."""
        filename = f"{self.results_dir}/{test_suite_name}_{variant_name}_{int(time.time())}.json"
        
        # Convert result to dict
        result_dict = {
            "variant_name": result.variant_name,
            "success_rate": result.success_rate,
            "avg_latency_ms": result.avg_latency_ms,
            "avg_token_count": result.avg_token_count,
            "case_results": result.case_results,
            "timestamp": result.timestamp
        }
        
        with open(filename, "w") as f:
            json.dump(result_dict, f, indent=2)
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the response into a structured output."""
        # Try to parse as JSON
        try:
            return json.loads(response)
        except:
            # Fallback: extract fields using regex
            import re
            result = {}
            
            # Match field name: value patterns
            pattern = r"([a-zA-Z_]+):\s*(.+?)(?:\n\s*[a-zA-Z_]+:|\Z)"
            matches = re.findall(pattern, response, re.DOTALL)
            
            for field, value in matches:
                result[field.strip()] = value.strip()
            
            return result
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        try:
            import tiktoken
            encoder = tiktoken.encoding_for_model("gpt-4")
            return len(encoder.encode(text))
        except:
            # Fallback: estimate 1 token per 4 characters
            return len(text) // 4
```

3. **Variant Generator**

```python
# src/flock/prompting/testing/variant_generator.py
from typing import Dict, Any, List
from flock.core.flock_agent import FlockAgent
from flock.prompting.testing.ab_tester import PromptVariant
from flock.prompting.optimization.optimized_builder import OptimizedPromptBuilder

class VariantGenerator:
    """Generates prompt variants for A/B testing."""
    
    def __init__(self, agent: FlockAgent):
        self.agent = agent
    
    def generate_template_variants(self) -> List[PromptVariant]:
        """Generate variants using different templates."""
        variants = []
        
        # Standard template variant
        standard_builder = OptimizedPromptBuilder()
        variants.append(PromptVariant(
            name="standard_template",
            builder_func=lambda inputs: standard_builder.build_prompt(
                self.agent, inputs, template_name="standard"
            ),
            description="Standard template with default settings"
        ))
        
        # ReAct template variant
        react_builder = OptimizedPromptBuilder()
        variants.append(PromptVariant(
            name="react_template",
            builder_func=lambda inputs: react_builder.build_prompt(
                self.agent, inputs, template_name="react"
            ),
            description="ReAct template for tool use"
        ))
        
        # Creative template variant
        creative_builder = OptimizedPromptBuilder()
        variants.append(PromptVariant(
            name="creative_template",
            builder_func=lambda inputs: creative_builder.build_prompt(
                self.agent, inputs, template_name="creative"
            ),
            description="Creative template for open-ended tasks"
        ))
        
        return variants
    
    def generate_optimization_variants(self) -> List[PromptVariant]:
        """Generate variants with different optimization strategies."""
        variants = []
        
        # Baseline: no optimization
        baseline_builder = OptimizedPromptBuilder()
        variants.append(PromptVariant(
            name="baseline",
            builder_func=lambda inputs: baseline_builder.build_prompt(
                self.agent, inputs
            ),
            description="Baseline with no special optimization"
        ))
        
        # Token budget optimization
        token_builder = OptimizedPromptBuilder(max_tokens=4000)
        variants.append(PromptVariant(
            name="token_optimized",
            builder_func=lambda inputs: token_builder.build_prompt(
                self.agent, inputs
            ),
            description="Optimized for token efficiency"
        ))
        
        # With examples
        examples_builder = OptimizedPromptBuilder()
        examples = [
            {
                "input": {"key1": "value1"},
                "output": {"result": "example output 1"}
            },
            {
                "input": {"key2": "value2"},
                "output": {"result": "example output 2"}
            }
        ]
        variants.append(PromptVariant(
            name="with_examples",
            builder_func=lambda inputs: examples_builder.build_prompt(
                self.agent, inputs, examples=examples
            ),
            description="Includes specific examples"
        ))
        
        return variants
    
    def generate_custom_variants(self, 
                                base_builder: OptimizedPromptBuilder,
                                variant_params: List[Dict[str, Any]]) -> List[PromptVariant]:
        """Generate custom variants based on provided parameters."""
        variants = []
        
        for i, params in enumerate(variant_params):
            # Create a copy of the base builder
            name = params.pop("name", f"custom_variant_{i}")
            description = params.pop("description", f"Custom variant {i}")
            
            # Create a closure to capture the params
            def make_builder_func(params_copy):
                return lambda inputs: base_builder.build_prompt(
                    self.agent, inputs, **params_copy
                )
            
            variants.append(PromptVariant(
                name=name,
                builder_func=make_builder_func(params.copy()),
                description=description,
                parameters=params
            ))
        
        return variants
```

#### Implementation Steps:

1. Build test case and test suite infrastructure
2. Implement A/B test runner
3. Create variant generator
4. Add utilities for analyzing test results
5. Create integration tests for the A/B testing framework

#### Success Criteria:
- Ability to define and run test cases
- Automatic comparison of different prompt strategies
- Statistical validation of results
- Easy visualization of performance differences

---

### Phase 6: Advanced Optimization Techniques (2-3 weeks)

**Goal:** Implement sophisticated prompt optimization techniques for maximum performance.

#### Components to Implement:

1. **Prompt Compression**

```python
# src/flock/prompting/optimization/compression.py
import re
from typing import Dict, Any, List, Tuple

class PromptCompressor:
    """Implements various prompt compression techniques."""
    
    def compress(self, 
               prompt: str,
               target_reduction: float = 0.3,
               preserve_sections: List[str] = None) -> str:
        """Compress a prompt to reduce token usage while preserving meaning."""
        # If no target reduction, return as is
        if target_reduction <= 0:
            return prompt
            
        # Split into sections
        sections = self._split_into_sections(prompt)
        
        # Identify sections to preserve
        preserve_sections = preserve_sections or ["INPUT VALUES:", "OUTPUT SCHEMA:"]
        preserved = {section for section in sections.keys() 
                   if any(p in section for p in preserve_sections)}
        
        # Apply compression techniques progressively until target reduction is reached
        compressed_sections = sections.copy()
        current_length = sum(len(text) for text in sections.values())
        target_length = current_length * (1 - target_reduction)
        
        # Determine sections to compress and their order
        compress_candidates = [(section, text) for section, text in sections.items() 
                             if section not in preserved]
        compress_candidates.sort(key=lambda x: (x[0] not in preserved, len(x[1])), reverse=True)
        
        # Apply compression techniques
        for section, text in compress_candidates:
            if self._calculate_length(compressed_sections) <= target_length:
                break
                
            # Apply appropriate technique based on section
            if "EXAMPLES:" in section:
                compressed_sections[section] = self._compress_examples(text)
            elif "TOOLS:" in section:
                compressed_sections[section] = self._compress_tools(text)
            elif "SCHEMA:" in section:
                compressed_sections[section] = self._compress_schema(text)
            else:
                compressed_sections[section] = self._compress_generic(text)
        
        # Reassemble prompt
        return self._reassemble_prompt(compressed_sections)
    
    def _split_into_sections(self, prompt: str) -> Dict[str, str]:
        """Split a prompt into logical sections."""
        # Find section headers
        section_pattern = r"([A-Z ]+:)\n"
        sections = {}
        
        # Find all section headers
        headers = re.findall(section_pattern, prompt)
        
        # Split using the headers
        parts = re.split(section_pattern, prompt)
        
        # Assemble sections
        if parts[0]:
            sections["PREAMBLE"] = parts[0]
            
        for i in range(0, len(headers)):
            header = headers[i]
            content_idx = (i * 2) + 1
            if content_idx < len(parts):
                sections[header] = parts[content_idx]
        
        return sections
    
    def _reassemble_prompt(self, sections: Dict[str, str]) -> str:
        """Reassemble sections into a prompt."""
        # Special handling for preamble
        result = []
        if "PREAMBLE" in sections:
            result.append(sections["PREAMBLE"])
            del sections["PREAMBLE"]
        
        # Add remaining sections
        for header, content in sections.items():
            result.append(f"{header}\n{content}")
        
        return "".join(result)
    
    def _calculate_length(self, sections: Dict[str, str]) -> int:
        """Calculate the total length of all sections."""
        return sum(len(text) for text in sections.values())
    
    def _compress_examples(self, examples_text: str) -> str:
        """Compress examples section."""
        lines = examples_text.split("\n")
        result = []
        
        # Keep only one example
        in_example = False
        example_count = 0
        
        for line in lines:
            if line.strip().startswith("Example "):
                in_example = True
                example_count += 1
                if example_count > 1:
                    in_example = False
                    continue
            
            if in_example or not line.strip().startswith("Example "):
                result.append(line)
        
        return "\n".join(result)
    
    def _compress_tools(self, tools_text: str) -> str:
        """Compress tools section."""
        tools = re.split(r"\n\n(?=\w+\()", tools_text)
        result = []
        
        for tool in tools:
            lines = tool.split("\n")
            # Keep only the function signature and first line of description
            if len(lines) > 0:
                result.append(lines[0])  # Function signature
            if len(lines) > 1:
                # Take only first sentence of description
                desc = lines[1].split(". ")[0] + "."
                result.append(desc)
            result.append("")  # Empty line between tools
        
        return "\n".join(result)
    
    def _compress_schema(self, schema_text: str) -> str:
        """Compress schema section by shortening descriptions."""
        lines = schema_text.split("\n")
        result = []
        
        for line in lines:
            if "|" in line:
                # Shorten description
                parts = line.split("|", 1)
                field_def = parts[0].strip()
                description = parts[1].strip()
                
                # Take only first few words
                words = description.split()
                short_desc = " ".join(words[:3]) + "..."
                result.append(f"{field_def} | {short_desc}")
            else:
                result.append(line)
        
        return "\n".join(result)
    
    def _compress_generic(self, text: str) -> str:
        """Apply generic compression techniques to any text."""
        # Remove redundant spaces
        text = re.sub(r"\s+", " ", text)
        
        # Remove filler phrases
        fillers = [
            r"In order to",
            r"Please note that",
            r"Keep in mind that",
            r"It is important to",
            r"Remember to",
            r"Make sure to",
            r"As you can see",
        ]
        for filler in fillers:
            text = re.sub(filler, "", text)
        
        # Shorten paragraphs
        if len(text) > 200:
            # Keep first and last sentence
            sentences = re.split(r'(?<=[.!?])\s+', text)
            if len(sentences) > 2:
                text = sentences[0] + " ... " + sentences[-1]
        
        return text
```

2. **Semantic Example Selection**

```python
# src/flock/prompting/optimization/semantic_selection.py
from typing import Dict, Any, List, Optional
import random
import numpy as np

class SemanticExampleSelector:
    """Selects examples based on semantic similarity to the current input."""
    
    def __init__(self, 
                model_name: str = "all-MiniLM-L6-v2",
                k: int = 2,
                similarity_threshold: float = 0.5):
        self.model_name = model_name
        self.k = k
        self.similarity_threshold = similarity_threshold
        self._embedding_model = None
    
    def select_examples(self, 
                      candidate_examples: List[Dict[str, Any]],
                      current_input: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Select examples based on semantic similarity."""
        if not candidate_examples:
            return []
            
        # Encode the current input
        current_embedding = self._encode_input(current_input)
        
        # Encode each example
        example_embeddings = []
        for example in candidate_examples:
            example_embedding = self._encode_input(example.get("input", {}))
            example_embeddings.append(example_embedding)
        
        # Calculate similarities
        similarities = []
        for embedding in example_embeddings:
            similarity = self._calculate_similarity(current_embedding, embedding)
            similarities.append(similarity)
        
        # Filter by threshold
        filtered_examples = []
        for i, similarity in enumerate(similarities):
            if similarity >= self.similarity_threshold:
                filtered_examples.append((candidate_examples[i], similarity))
        
        # Sort by similarity
        filtered_examples.sort(key=lambda x: x[1], reverse=True)
        
        # Select top k
        selected = [ex for ex, _ in filtered_examples[:self.k]]
        
        # If we don't have enough examples after filtering, add random ones
        if len(selected) < self.k and len(candidate_examples) > len(selected):
            remaining = [
                ex for ex in candidate_examples 
                if ex not in selected
            ]
            needed = self.k - len(selected)
            selected.extend(random.sample(remaining, min(needed, len(remaining))))
        
        return selected
    
    def _encode_input(self, input_data: Dict[str, Any]) -> np.ndarray:
        """Encode the input data as a vector."""
        # Initialize the embedding model if needed
        if not self._embedding_model:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(self.model_name)
        
        # Convert input to string
        input_str = " ".join(f"{k}: {v}" for k, v in input_data.items())
        
        # Encode the input
        return self._embedding_model.encode(input_str)
    
    def _calculate_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))
```

3. **Adaptive Learning**

```python
# src/flock/prompting/optimization/adaptive_learning.py
from typing import Dict, Any, List, Optional
import json
import os
import time

class AdaptiveLearner:
    """Learns from successful and failed attempts to optimize prompts."""
    
    def __init__(self, storage_path: str = "adaptive_learning.json"):
        self.storage_path = storage_path
        self.data = self._load_data()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load learning data from storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except:
                return self._initialize_data()
        else:
            return self._initialize_data()
    
    def _initialize_data(self) -> Dict[str, Any]:
        """Initialize data structure."""
        return {
            "agent_stats": {},
            "template_stats": {},
            "parameter_impact": {},
            "version": 1,
            "last_updated": time.time()
        }
    
    def record_attempt(self, 
                     agent_name: str,
                     template_name: str,
                     parameters: Dict[str, Any],
                     success: bool,
                     metrics: Dict[str, Any]) -> None:
        """Record a prompt attempt with its success or failure."""
        # Initialize agent stats if needed
        if agent_name not in self.data["agent_stats"]:
            self.data["agent_stats"][agent_name] = {
                "total_attempts": 0,
                "successful_attempts": 0,
                "templates": {}
            }
        
        # Update agent stats
        self.data["agent_stats"][agent_name]["total_attempts"] += 1
        if success:
            self.data["agent_stats"][agent_name]["successful_attempts"] += 1
        
        # Update template stats for this agent
        if template_name not in self.data["agent_stats"][agent_name]["templates"]:
            self.data["agent_stats"][agent_name]["templates"][template_name] = {
                "total_attempts": 0,
                "successful_attempts": 0,
                "avg_tokens": 0,
                "avg_latency": 0
            }
        
        template_stats = self.data["agent_stats"][agent_name]["templates"][template_name]
        template_stats["total_attempts"] += 1
        if success:
            template_stats["successful_attempts"] += 1
        
        # Update global template stats
        if template_name not in self.data["template_stats"]:
            self.data["template_stats"][template_name] = {
                "total_attempts": 0,
                "successful_attempts": 0
            }
        
        self.data["template_stats"][template_name]["total_attempts"] += 1
        if success:
            self.data["template_stats"][template_name]["successful_attempts"] += 1
        
        # Update parameter impact
        for param_name, param_value in parameters.items():
            param_key = f"{param_name}:{str(param_value)}"
            if param_key not in self.data["parameter_impact"]:
                self.data["parameter_impact"][param_key] = {
                    "total_attempts": 0,
                    "successful_attempts": 0
                }
            
            self.data["parameter_impact"][param_key]["total_attempts"] += 1
            if success:
                self.data["parameter_impact"][param_key]["successful_attempts"] += 1
        
        # Update metrics
        if "avg_tokens" in metrics:
            template_stats["avg_tokens"] = (
                (template_stats["avg_tokens"] * (template_stats["total_attempts"] - 1) + 
                 metrics["avg_tokens"]) / template_stats["total_attempts"]
            )
        
        if "avg_latency" in metrics:
            template_stats["avg_latency"] = (
                (template_stats["avg_latency"] * (template_stats["total_attempts"] - 1) + 
                 metrics["avg_latency"]) / template_stats["total_attempts"]
            )
        
        # Update timestamp
        self.data["last_updated"] = time.time()
        
        # Save data
        self._save_data()
    
    def _save_data(self) -> None:
        """Save learning data to storage."""
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(self.data, f, indent=2)
    
    def get_best_template(self, agent_name: str) -> Optional[str]:
        """Get the best performing template for an agent."""
        if agent_name not in self.data["agent_stats"]:
            return None
            
        templates = self.data["agent_stats"][agent_name]["templates"]
        if not templates:
            return None
            
        # Calculate success rates
        template_scores = {}
        for name, stats in templates.items():
            if stats["total_attempts"] == 0:
                continue
                
            success_rate = (
                stats["successful_attempts"] / stats["total_attempts"]
                if stats["total_attempts"] > 0 else 0
            )
            
            # Apply a confidence factor based on number of attempts
            confidence = min(stats["total_attempts"] / 10, 1.0)
            adjusted_rate = success_rate * confidence
            
            template_scores[name] = adjusted_rate
        
        if not template_scores:
            return None
            
        # Return the template with the highest score
        return max(template_scores.items(), key=lambda x: x[1])[0]
    
    def get_parameter_recommendations(self, agent_name: str) -> Dict[str, Any]:
        """Get parameter recommendations based on learning data."""
        recommendations = {}
        
        # Analyze parameter impact
        for param_key, stats in self.data["parameter_impact"].items():
            if stats["total_attempts"] < 5:
                continue  # Not enough data
                
            success_rate = (
                stats["successful_attempts"] / stats["total_attempts"]
                if stats["total_attempts"] > 0 else 0
            )
            
            param_name, param_value_str = param_key.split(":", 1)
            
            # Convert value string to appropriate type
            try:
                if param_value_str.lower() == "true":
                    param_value = True
                elif param_value_str.lower() == "false":
                    param_value = False
                elif param_value_str.isdigit():
                    param_value = int(param_value_str)
                elif "." in param_value_str and all(
                    part.isdigit() for part in param_value_str.split(".", 1)
                ):
                    param_value = float(param_value_str)
                else:
                    param_value = param_value_str
            except:
                param_value = param_value_str
            
            if param_name not in recommendations:
                recommendations[param_name] = []
                
            recommendations[param_name].append({
                "value": param_value,
                "success_rate": success_rate,
                "sample_size": stats["total_attempts"]
            })
        
        # Sort each parameter's recommendations by success rate
        for param_name in recommendations:
            recommendations[param_name].sort(
                key=lambda x: (x["success_rate"], x["sample_size"]),
                reverse=True
            )
        
        return recommendations
```

4. **Smart Output Parser**

```python
# src/flock/prompting/optimization/output_parser.py
import re
import json
from typing import Dict, Any, List, Optional, Type, Union
import pydantic
from flock.prompting.schema_parser import parse_output_schema

class OutputParsingStrategy:
    """Base class for output parsing strategies."""
    
    def parse(self, text: str, schema: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse text into structured output according to schema."""
        raise NotImplementedError()

class JSONParsingStrategy(OutputParsingStrategy):
    """Attempts to parse output as JSON."""
    
    def parse(self, text: str, schema: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse text as JSON."""
        # First, try to find a JSON block
        json_pattern = r'```(?:json)?\s*({[\s\S]*?})```'
        json_match = re.search(json_pattern, text)
        
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        # Try the whole text
        try:
            return json.loads(text)
        except:
            # Try to fix common JSON errors
            fixed_text = self._fix_json(text)
            try:
                return json.loads(fixed_text)
            except:
                raise ValueError("Could not parse as JSON")
    
    def _fix_json(self, text: str) -> str:
        """Attempt to fix common JSON formatting errors."""
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Ensure the text starts and ends with curly braces
        if not text.startswith("{"):
            text = "{" + text
        if not text.endswith("}"):
            text = text + "}"
        
        # Fix missing quotes around keys
        text = re.sub(r'(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):(\s*)', r'\1"\2"\3:\4', text)
        
        # Fix single quotes
        text = text.replace("'", '"')
        
        # Fix trailing commas
        text = re.sub(r',(\s*})', r'\1', text)
        
        return text

class KeyValueParsingStrategy(OutputParsingStrategy):
    """Parses output as key-value pairs."""
    
    def parse(self, text: str, schema: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse text as key