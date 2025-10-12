"""
🌐 LESSON 03: The Web Detective - MCP Tools & Playwright
=========================================================

🎯 LEARNING OBJECTIVES:
----------------------
In this lesson, you'll learn:
1. How to integrate external tools using Model Context Protocol (MCP)
2. How to give agents web browsing capabilities with Playwright
3. How tools extend agent capabilities beyond LLM knowledge
4. How to build research agents that gather real-time information

🎬 THE SCENARIO:
---------------
You're building an AI research assistant that can browse the web to gather
information. Using Playwright MCP, your agent can:
- Navigate to websites
- Extract content
- Take screenshots
- Fill forms and interact with pages

We'll build a "Tech Trend Detective" that researches emerging technologies
by actually browsing websites and summarizing what it finds.

⏱️  TIME: 20 minutes
💡 COMPLEXITY: ⭐⭐⭐ Intermediate-Advanced

🔧 PREREQUISITES:
- Node.js installed (for npx)
- Internet connection (agent will browse real websites!)

Let's investigate! 🕵️👇
"""

import asyncio

from pydantic import BaseModel, Field

from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 STEP 1: Define Research Artifacts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@flock_type
class ResearchQuery(BaseModel):
    """
    INPUT: What we want the detective to investigate

    This triggers the research agent to start browsing.
    """

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

    This contains everything discovered during the investigation.

    🔥 KEY INSIGHT:
    The agent will use Playwright to actually browse websites,
    extract content, and summarize findings. This goes beyond
    what an LLM can do from its training data!
    """

    topic: str = Field(description="The researched topic")

    executive_summary: str = Field(
        description="High-level summary of findings (2-3 sentences)",
        min_length=100,
        max_length=500,
    )

    key_findings: list[str] = Field(
        description="Bullet points of important discoveries",
        min_length=3,
        max_length=10,
    )

    sources_visited: list[dict[str, str]] = Field(
        description="URLs visited with titles and key excerpts",
        examples=[[{"url": "...", "title": "...", "excerpt": "..."}]],
    )

    trends_identified: list[str] = Field(
        description="Emerging trends or patterns noticed",
        min_length=1,
    )

    confidence_level: float = Field(
        description="How confident the detective is in the findings (0.0-1.0)",
        ge=0.0,
        le=1.0,
    )

    research_timestamp: str = Field(
        description="When the research was conducted",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 STEP 2: Create Orchestrator with MCP Integration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock("openai/gpt-4.1")

# 🔌 STEP 2A: Add Playwright MCP Server
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 💡 WHAT IS MCP (Model Context Protocol)?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MCP is a standardized protocol for giving LLMs access to external tools and data.
# Think of it as "function calling on steroids" - instead of defining functions
# manually, you connect to MCP servers that provide pre-built tool suites.
#
# Playwright MCP gives your agent:
# - playwright_navigate(url) - Visit a webpage
# - playwright_screenshot(name) - Capture what's on screen
# - playwright_click(selector) - Interact with elements
# - playwright_fill(selector, value) - Fill forms
# - playwright_evaluate(script) - Run JavaScript on page
# - And more!

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

# 🎯 WHAT JUST HAPPENED?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# We registered an MCP server called "browse_web" that runs Playwright.
# When an agent declares `.with_mcps(["browse_web"])`, it automatically gets
# access to all Playwright functions as callable tools!
#
# The LLM can now:
# 1. Decide which websites to visit
# 2. Navigate to those URLs
# 3. Extract content from pages
# 4. Take screenshots if needed
# 5. Interact with dynamic content
#
# All without you writing a single web scraping function!

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🕵️ STEP 3: Define the Web Detective Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

# 💡 WHAT HAPPENED WITH .with_mcps()?
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# By adding `.with_mcps(["browse_web"])`, we told Flock:
# "This agent can use all tools from the 'browse_web' MCP server"
#
# During execution, the LLM will:
# 1. See the ResearchQuery input
# 2. Decide it needs to browse websites
# 3. Call playwright_navigate("https://...") to visit pages
# 4. Extract text content from those pages
# 5. Analyze what it found
# 6. Produce a structured WebResearchReport
#
# 🆚 VS MANUAL TOOL DEFINITION:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ❌ Traditional way:
#     @flock_tool
#     def navigate(url: str):
#         # Write your own browser automation
#         # Handle errors, timeouts, authentication
#         # Parse HTML, extract text
#         # ... 200 lines of code
#
# ✅ MCP way:
#     .with_mcps(["browse_web"])
#     # Get professional-grade browser automation instantly!

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 4: Run the Investigation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    Watch an AI agent browse the web in real-time!

    The agent will:
    1. Receive the research query
    2. Decide which websites to visit
    3. Use Playwright to navigate and extract content
    4. Synthesize findings into a report
    """

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

    print("=" * 70)
    print("📋 RESEARCH QUERY")
    print("=" * 70)
    print(f"Topic: {query.topic}")
    print(f"Depth: {query.depth}")
    if query.target_urls:
        print(f"Suggested URLs ({len(query.target_urls)}):")
        for url in query.target_urls:
            print(f"  - {url}")
    print("=" * 70)
    print()

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

        print("\n" + "=" * 70)
        print("📑 RESEARCH REPORT COMPLETE")
        print("=" * 70)
        print(f"\n🎯 Topic: {report.topic}")
        print("\n📝 Executive Summary:")
        print(f"   {report.executive_summary}")

        print("\n🔍 Key Findings:")
        for i, finding in enumerate(report.key_findings, 1):
            print(f"   {i}. {finding}")

        print(f"\n📚 Sources Visited ({len(report.sources_visited)}):")
        for source in report.sources_visited:
            print(f"\n   🌐 {source.get('title', 'Unknown')}")
            print(f"      URL: {source.get('url', 'N/A')}")
            excerpt = source.get("excerpt", "")
            if excerpt:
                # Truncate long excerpts
                excerpt_preview = excerpt[:150] + "..." if len(excerpt) > 150 else excerpt
                print(f"      Excerpt: {excerpt_preview}")

        print("\n📈 Trends Identified:")
        for trend in report.trends_identified:
            print(f"   • {trend}")

        print(f"\n🎯 Confidence Level: {report.confidence_level:.0%}")
        print(f"📅 Research Completed: {report.research_timestamp}")
        print("=" * 70)
    else:
        print("❌ No research report generated (check logs for errors)")

    print("\n✨ Investigation complete!")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 LEARNING CHECKPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
🎉 CONGRATULATIONS! You just built a web-browsing AI agent with MCP!

🔑 KEY TAKEAWAYS:
-----------------

1️⃣ MCP ABSTRACTION
   - Model Context Protocol provides standardized tool access
   - No need to write custom web scraping code
   - Professional-grade tools out of the box

2️⃣ PLAYWRIGHT CAPABILITIES
   - Real browser automation (not just HTTP requests)
   - Can handle JavaScript-rendered content
   - Can interact with dynamic pages
   - Can take screenshots and extract structured data

3️⃣ TOOL INTEGRATION PATTERN
   - flock.add_mcp() registers the tool server
   - agent.with_mcps([...]) gives agent access
   - LLM decides when and how to use tools
   - All automatic!

4️⃣ BEYOND TRAINING DATA
   - LLMs are limited to their training cutoff
   - Tools let agents access real-time information
   - Agents can browse, search, and interact
   - True "agentic" behavior!

🆚 VS TRADITIONAL APPROACHES:
-----------------------------

❌ RAG (Retrieval Augmented Generation):
```python
# Pre-index documents, search at query time
embeddings = embed_documents(docs)
results = vector_search(query, embeddings)
# Limited to pre-indexed content
```

❌ Manual Tool Definition:
```python
@flock_tool
def scrape_website(url: str):
    response = requests.get(url)
    soup = BeautifulSoup(response.text)
    # Handle errors, timeouts, JS rendering...
    # 200+ lines of fragile code
```

✅ MCP + Flock:
```python
flock.add_mcp("browse_web", ...)
agent.with_mcps(["browse_web"])
# Get professional browser automation!
```

💡 AVAILABLE MCP SERVERS:
-------------------------
Playwright is just one of many MCP servers. Others include:

- @modelcontextprotocol/server-filesystem - File system access
- @modelcontextprotocol/server-github - GitHub API
- @modelcontextprotocol/server-google-maps - Maps and location
- @modelcontextprotocol/server-postgres - Database queries
- @modelcontextprotocol/server-slack - Slack integration
- And many more at https://github.com/modelcontextprotocol

🧪 EXPERIMENT IDEAS:
-------------------

1. Add Multiple MCP Servers:
```python
flock.add_mcp("browse_web", ...)
flock.add_mcp("filesystem", ...)
agent.with_mcps(["browse_web", "filesystem"])
# Agent can browse AND save findings to files!
```

2. Create a Competitive Intelligence Agent:
   - Research competitor websites
   - Extract pricing information
   - Generate comparison reports

3. Build a News Aggregator:
   - Visit multiple news sites
   - Extract headlines and summaries
   - Identify trending topics

4. Make a Product Research Assistant:
   - Browse e-commerce sites
   - Compare prices and reviews
   - Generate buying recommendations

5. Enable Tracing to See Tool Calls:
```bash
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
# Query traces to see exactly what Playwright did:
SELECT attributes->>'$.function' as tool_name
FROM spans
WHERE attributes->>'$.function' LIKE 'playwright%'
```

⚠️  IMPORTANT NOTES:
-------------------

1. **Rate Limiting**: Be respectful when browsing websites
   - Don't hammer servers with requests
   - Add delays between navigations if needed

2. **Error Handling**: Websites can be flaky
   - Pages may be down
   - Content structure may change
   - Agents should handle failures gracefully

3. **Cost Awareness**: Tool use increases token usage
   - Each tool call is a round-trip to the LLM
   - Complex research can be expensive
   - Consider caching results

4. **Privacy & Ethics**:
   - Respect robots.txt
   - Don't scrape private/authenticated content
   - Be transparent about AI usage

📈 NEXT LESSON:
--------------
Lesson 04: The Debate Club
- Learn feedback loops and iterative refinement
- Build agents that critique and improve their own outputs
- Understand self-triggering safety mechanisms

🎯 READY TO CONTINUE?
Run: uv run examples/claudes-flock-course/lesson_04_debate_club.py
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
