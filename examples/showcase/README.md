# Showcase Examples

**Purpose**: Engaging demonstrations for workshops, demos, and onboarding

These examples showcase Flock-Flow's capabilities in accessible, engaging ways. They're designed to:
- Demonstrate real-world use cases
- Tell a clear story with narrative flow
- Provide visual output and progress indicators
- Minimize technical complexity
- Create "wow moments" for audiences

## Examples in This Directory

### `01_hello_flock.py` - Movie Creation Pipeline
**Purpose**: Demonstrate basic multi-agent pipeline
**Story**: Transform a simple idea into a complete movie concept with tagline
**Flow**: Idea → Movie Generator → Tagline Creator
**Features**: Typed artifacts, auto-connected agents via blackboard
**Wow Factor**: See LLM agents collaborate to create creative content

### `02_blog_review.py` - Blog Review Loop
**Purpose**: Show iterative agent improvement cycles
**Story**: AI blog writer gets feedback from SEO optimizer and iterates until approved
**Flow**: Idea → Blog Writer ↔ SEO Reviewer (loop until approved)
**Features**: Multi-turn conversation, feedback loops, DSPy engine integration
**Wow Factor**: Watch agents collaborate and improve content through multiple iterations

### `03_mcp_tools.py` - MCP Integration
**Purpose**: Demonstrate Model Context Protocol (MCP) server integration
**Story**: Analyze websites using external MCP tools
**Flow**: URL → Website Analyzer (using MCP tools) → Analysis Report
**Features**: MCP server integration, external tool calling, real-world data fetching
**Wow Factor**: See agents leverage external services seamlessly

### `04_dashboard.py` - Real-Time Dashboard (NEW!)
**Purpose**: Showcase the live dashboard visualization
**Story**: Watch the blog review pipeline execute with real-time visual feedback
**Flow**: Same as `02_blog_review.py` but with live dashboard UI
**Features**:
- Real-time graph visualization (Agent View & Blackboard View)
- Live streaming LLM output
- Event log with filtering
- Publish/Invoke controls from browser
- Session persistence (positions saved)

**Wow Factor**: Open your browser and watch AI agents work in real-time!

## Running Showcase Examples

```bash
# From project root
cd /home/ara/work/flock-flow

# Basic pipeline (runs in terminal)
uv run examples/showcase/01_hello_flock.py

# Review loop (terminal output)
uv run examples/showcase/02_blog_review.py

# MCP integration (requires read-website-fast-mcp-server)
uv run examples/showcase/03_mcp_tools.py

# Real-time dashboard (opens browser automatically!)
uv run examples/showcase/04_dashboard.py
```

## Creating New Showcase Examples

**Checklist for showcase examples**:
- [ ] Tell a compelling story (not just technical demonstration)
- [ ] Minimize setup complexity (easy to run)
- [ ] Include progress indicators and visual feedback
- [ ] Create "wow moments" (surprising or delightful outputs)
- [ ] Add clear narrative comments explaining what's happening
- [ ] Keep execution time reasonable (< 2 minutes)
- [ ] Test on fresh environments

**Template**:
```python
"""
[Example Name]
===============

[Engaging description of what this example demonstrates]

Story: [Narrative description of the workflow]
"""

import asyncio
from flock.orchestrator import Flock
from flock.registry import flock_type
# ... imports ...

# 1. Define artifacts with comments
@flock_type
class Input(BaseModel):
    """[What this represents in the story]"""
    # ... fields ...

# 2. Create orchestrator
orchestrator = Flock()

# 3. Define agents with narrative comments
# "First, we need an agent to..."
agent1 = orchestrator.agent("name").consumes(Input).publishes(Output)

# 4. Publish initial artifact with progress output
print("🎬 Starting the [story]...")
orchestrator.publish(Input(...))

# 5. Run with feedback
asyncio.run(orchestrator.serve(dashboard=True))  # Auto-opens dashboard!
```
