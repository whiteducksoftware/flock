# Conditional Routing: Web Research with MCP

**Difficulty:** ⭐⭐⭐ Intermediate-Advanced | **Time:** 30 minutes

Learn how to give agents web-browsing capabilities using Model Context Protocol (MCP) and Playwright. Build research agents that gather real-time information beyond LLM training data.

**Prerequisites:**

- Complete [Multi-Agent Workflow](multi-agent-workflow.md)
- Node.js installed (for MCP)
- Internet connection

## What You'll Build

A **Tech Trend Detective** that researches emerging technologies by actually browsing websites and summarizing findings.

## What is MCP (Model Context Protocol)?

MCP is a standardized protocol for giving LLMs access to external tools and data.

Think of it as **"function calling on steroids"**—instead of defining functions manually, you connect to MCP servers that provide pre-built tool suites.

**Playwright MCP gives your agent:**

- `playwright_navigate(url)` - Visit a webpage
- `playwright_screenshot(name)` - Capture what's on screen
- `playwright_click(selector)` - Interact with elements
- `playwright_fill(selector, value)` - Fill forms
- `playwright_evaluate(script)` - Run JavaScript on page
- And more!

## Step 1: Define Research Artifacts

```python
from pydantic import BaseModel, Field
from flock import Flock
from flock.registry import flock_type

@flock_type
class ResearchQuery(BaseModel):
    """INPUT: What we want the detective to investigate"""
    topic: str = Field(
        description="The technology or trend to research",
        examples=["quantum computing", "edge AI", "serverless databases"],
    )
    target_urls: list[str] = Field(
        description="Specific URLs to investigate (optional)",
        default_factory=list,
    )
    depth: str = Field(
        description="Research depth: quick, standard, or deep",
        default="standard",
        pattern="^(quick|standard|deep)$",
    )

@flock_type
class WebResearchReport(BaseModel):
    """
    OUTPUT: The detective's findings from browsing the web

    🔥 KEY INSIGHT:
    The agent will use Playwright to actually browse websites,
    extract content, and summarize findings. This goes beyond
    what an LLM can do from its training data!
    """
    topic: str
    executive_summary: str = Field(min_length=100, max_length=500)
    key_findings: list[str] = Field(min_length=3, max_length=10)
    sources_visited: list[dict[str, str]] = Field(
        description="URLs visited with titles and key excerpts"
    )
    trends_identified: list[str] = Field(min_length=1)
    confidence_level: float = Field(ge=0.0, le=1.0)
    research_timestamp: str
```

## Step 2: Add MCP Integration

```python
from flock.mcp import StdioServerParameters

flock = Flock("openai/gpt-4.1")

# 🔌 Add Playwright MCP Server
flock.add_mcp(
    name="browse_web",
    enable_tools_feature=True,  # Expose MCP tools to agents
    connection_params=StdioServerParameters(
        command="npx",  # Use npx to run the MCP server
        args=[
            "-y",  # Auto-install if needed
            "@playwright/mcp@latest",  # Playwright MCP package
        ],
    ),
)
```

**🎯 What Just Happened?**

We registered an MCP server called "browse_web" that runs Playwright.

When an agent declares `.with_mcps(["browse_web"])`, it automatically gets access to all Playwright functions as callable tools!

The LLM can now:

1. Decide which websites to visit
2. Navigate to those URLs
3. Extract content from pages
4. Take screenshots if needed
5. Interact with dynamic content

All without you writing a single web scraping function!

## Step 3: Define the Web Detective Agent

```python
web_detective = (
    flock.agent("web_detective")
    .description(
        "An expert web researcher who uses Playwright to browse websites, "
        "extract information, and synthesize findings into comprehensive reports. "
        "Skilled at identifying credible sources, cross-referencing information, "
        "and spotting emerging trends."
    )
    .consumes(ResearchQuery)
    .publishes(WebResearchReport)
    .with_mcps(["browse_web"])  # 🔥 THIS IS THE MAGIC LINE!
)
```

**💡 What Happened with `.with_mcps()`?**

By adding `.with_mcps(["browse_web"])`, we told Flock: "This agent can use all tools from the 'browse_web' MCP server"

During execution, the LLM will:

1. See the ResearchQuery input
2. Decide it needs to browse websites
3. Call `playwright_navigate("https://...")` to visit pages
4. Extract text content from those pages
5. Analyze what it found
6. Produce a structured WebResearchReport

## Comparison: Traditional vs MCP

### ❌ Traditional Way

```python
@flock_tool
def navigate(url: str):
    # Write your own browser automation
    # Handle errors, timeouts, authentication
    # Parse HTML, extract text
    # ... 200 lines of code
```

### ✅ MCP Way

```python
.with_mcps(["browse_web"])
# Get professional-grade browser automation instantly!
```

## Step 4: Run the Investigation

```python
async def main():
    print("🕵️ Starting Web Detective Investigation...\n")

    # 🎯 Create a research query
    query = ResearchQuery(
        topic="AI agent frameworks in 2025",
        target_urls=[
            "https://github.com/topics/ai-agents",
            "https://www.anthropic.com/",
        ],
        depth="standard",
    )

    print("🌐 Detective is browsing the web...")
    print("   (This will take 30-60 seconds as it visits real websites)\n")

    # 📤 Publish the query
    await flock.publish(query)

    # ⏳ Wait for the detective to complete the investigation
    # The agent will make multiple tool calls to Playwright during this time
    await flock.run_until_idle()

    # 📊 Retrieve the research report
    reports = await flock.store.get_artifacts_by_type("WebResearchReport")

    if reports:
        report = reports[-1].obj
        print(f"\n🎯 Topic: {report.topic}")
        print(f"\n📝 Summary: {report.executive_summary}")
        print(f"\n🔍 Key Findings:")
        for i, finding in enumerate(report.key_findings, 1):
            print(f"   {i}. {finding}")
        print(f"\n🎯 Confidence: {report.confidence_level:.0%}")
```

## What Makes This Powerful

### 1. Beyond Training Data

- LLMs are limited to their training cutoff
- Tools let agents access real-time information
- Agents can browse, search, and interact
- True "agentic" behavior!

### 2. Professional Browser Automation

- Real browser automation (not just HTTP requests)
- Can handle JavaScript-rendered content
- Can interact with dynamic pages
- Can take screenshots and extract structured data

### 3. Automatic Tool Selection

- LLM decides when and how to use tools
- Multiple tool calls in sequence
- Adaptive research strategies
- All automatic!

## Available MCP Servers

Playwright is just one of many MCP servers:

- `@modelcontextprotocol/server-filesystem` - File system access
- `@modelcontextprotocol/server-github` - GitHub API
- `@modelcontextprotocol/server-google-maps` - Maps and location
- `@modelcontextprotocol/server-postgres` - Database queries
- `@modelcontextprotocol/server-slack` - Slack integration
- And many more at https://github.com/modelcontextprotocol

## Key Takeaways

### 1. MCP Abstraction

- Model Context Protocol provides standardized tool access
- No need to write custom web scraping code
- Professional-grade tools out of the box

### 2. Tool Integration Pattern

- `flock.add_mcp()` registers the tool server
- `agent.with_mcps([...])` gives agent access
- LLM decides when and how to use tools
- All automatic!

### 3. Real-Time Information

- Not limited to training data
- Can access current information
- Adapts to changing web content

## Try It Yourself

**Challenge 1: Add Multiple MCP Servers**

```python
flock.add_mcp("browse_web", ...)
flock.add_mcp("filesystem", ...)
agent.with_mcps(["browse_web", "filesystem"])
# Agent can browse AND save findings to files!
```

**Challenge 2: Create a Competitive Intelligence Agent**

- Research competitor websites
- Extract pricing information
- Generate comparison reports

**Challenge 3: Enable Tracing to See Tool Calls**

```bash
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
# Query traces to see exactly what Playwright did:
python -c "
import duckdb
conn = duckdb.connect('.flock/traces.duckdb', read_only=True)
tools = conn.execute('''
    SELECT attributes->'$.function' as tool_name
    FROM spans
    WHERE attributes->'$.function' LIKE 'playwright%'
''').fetchall()
for tool in tools:
    print(tool[0])
"
```

## Important Notes

### ⚠️ Rate Limiting

Be respectful when browsing websites:

- Don't hammer servers with requests
- Add delays between navigations if needed

### ⚠️ Error Handling

Websites can be flaky:

- Pages may be down
- Content structure may change
- Agents should handle failures gracefully

### ⚠️ Cost Awareness

Tool use increases token usage:

- Each tool call is a round-trip to the LLM
- Complex research can be expensive
- Consider caching results

### ⚠️ Privacy & Ethics

- Respect robots.txt
- Don't scrape private/authenticated content
- Be transparent about AI usage

## Next Steps

Now that you can integrate external tools, let's scale to parallel processing!

[Continue to Advanced Patterns →](advanced-patterns.md){ .md-button .md-button--primary }

## Reference Links

- [MCP Integration Guide](../guides/agents.md#mcp-tools) - Complete MCP documentation
- [Agent API Reference](../reference/api/agent.md) - Agent builder methods
- [Patterns Guide](../guides/patterns.md) - Common MCP patterns
