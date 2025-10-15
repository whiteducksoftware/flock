"""
Analyze Workflow Example - Discover Patterns in Codebase

This example demonstrates the analysis workflow:
1. User provides a path and analysis area
2. Analysis specialists scan the code
3. Patterns are discovered (business rules, architecture, security)
4. Documentation is created in docs/patterns/

This shows how the blackboard pattern enables emergent discovery.
"""

import asyncio
from pathlib import Path

from flock.orchestrator import Flock

from agents import create_specialist_agents
from artifacts import AnalyzeRequest, DocumentationUpdate, PatternDiscovery
from mcp_config import configure_mcps


async def analyze_codebase():
    """
    Analyze a codebase and discover patterns.

    Flow:
    1. Publish AnalyzeRequest for different areas
    2. Analysis specialists scan code with filesystem MCP
    3. PatternDiscovery artifacts are created
    4. pattern_documenter aggregates and creates docs
    """
    print("\n" + "=" * 70)
    print("ANALYZE WORKFLOW - PATTERN DISCOVERY")
    print("=" * 70)

    # Target: Analyze our own spec-driven example!
    target_path = str(Path(__file__).parent)

    print(f"\n[TARGET] {target_path}")
    print("[GOAL] Discover architectural patterns in our spec-driven system")

    # ===========================================================================
    # SETUP
    # ===========================================================================

    print("\n[Step 1] Setting up Flock with MCP tools...")
    flock = Flock()

    # Configure MCP servers
    mcp_status = configure_mcps(flock)
    print(f"  + MCP Status: {sum(mcp_status.values())}/{len(mcp_status)} configured")

    if not mcp_status.get("filesystem"):
        print("\n[ERROR] Filesystem MCP required for analysis!")
        print("  Please install: npm install -g @modelcontextprotocol/server-filesystem")
        return

    # Create specialist agents
    print("\n[Step 2] Creating specialist agents...")
    agents = create_specialist_agents(flock)
    print(f"  + Created {len(agents)} specialist agents")

    # ===========================================================================
    # PHASE 1: PUBLISH ANALYSIS REQUESTS
    # ===========================================================================

    print("\n[Phase 1] Publishing analysis requests...")

    # Business analysis (looking for domain patterns)
    business_request = AnalyzeRequest(
        analysis_area="business",
        target_path=target_path,
        focus=(
            "Discover the domain model: What are the key entities? "
            "What are the business rules? How do artifacts flow through the system?"
        ),
    )
    await flock.publish(business_request)
    print("  + Published: Business analysis (domain model)")

    # Technical analysis (looking for architectural patterns)
    technical_request = AnalyzeRequest(
        analysis_area="technical",
        target_path=target_path,
        focus=(
            "Discover architectural patterns: How do agents subscribe? "
            "How does the blackboard coordinate? What are the key abstractions?"
        ),
    )
    await flock.publish(technical_request)
    print("  + Published: Technical analysis (architecture)")

    # Security analysis (looking for security patterns)
    security_request = AnalyzeRequest(
        analysis_area="security",
        target_path=target_path,
        focus=(
            "Identify security patterns: How are MCP tools restricted? "
            "What access control patterns are used? Are there any security concerns?"
        ),
    )
    await flock.publish(security_request)
    print("  + Published: Security analysis (access control)")

    # ===========================================================================
    # EXECUTE ANALYSIS
    # ===========================================================================

    print("\n[Executing] Running analysis specialists...")
    print("  NOTE: This will take several minutes as agents analyze the code!")
    print("  Press Ctrl+C to stop early and see partial results\n")

    try:
        # Run agents with timeout
        await asyncio.wait_for(flock.run_until_idle(), timeout=300.0)
        print("\n[SUCCESS] All analysis completed!")
    except asyncio.TimeoutError:
        print("\n[TIMEOUT] Analysis took longer than expected")
        print("  Some patterns may still be processing...")
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Stopping early to show partial results...")

    # ===========================================================================
    # PHASE 2: COLLECT DISCOVERED PATTERNS
    # ===========================================================================

    print("\n[Phase 2] Collecting discovered patterns...")
    patterns = await flock.store.get_by_type(PatternDiscovery)
    print(f"  + Found {len(patterns)} patterns")

    if patterns:
        print("\n[PATTERNS DISCOVERED]")
        for i, pattern in enumerate(patterns, 1):
            print(f"\n  {i}. {pattern.pattern_name} ({pattern.pattern_type})")
            print(f"     Context: {pattern.context[:100]}...")
            print(f"     Use cases: {len(pattern.use_cases)}")
            print(f"     Examples: {len(pattern.examples)}")
            print(f"     Related patterns: {len(pattern.related_patterns)}")

    # ===========================================================================
    # PHASE 3: CHECK FOR DOCUMENTATION
    # ===========================================================================

    print("\n[Phase 3] Checking for generated documentation...")
    docs = await flock.store.get_by_type(DocumentationUpdate)
    print(f"  + Found {len(docs)} documentation updates")

    if docs:
        for doc in docs:
            print(f"\n  [DOC] {doc.document_type}")
            print(f"    Path: {doc.document_path}")
            print(f"    Changes: {len(doc.changes_summary)}")

    # ===========================================================================
    # SUMMARY
    # ===========================================================================

    print("\n" + "=" * 70)
    print("[SUMMARY]")
    print("=" * 70)
    print(f"\nTarget Path: {target_path}")
    print(f"Analysis Requests: 3 (business, technical, security)")
    print(f"Patterns Discovered: {len(patterns)}")
    print(f"Documentation Created: {len(docs)}")

    if patterns:
        print("\n[KEY PATTERNS]")
        # Group by type
        by_type = {}
        for pattern in patterns:
            pattern_type = pattern.pattern_type
            if pattern_type not in by_type:
                by_type[pattern_type] = []
            by_type[pattern_type].append(pattern.pattern_name)

        for pattern_type, names in by_type.items():
            print(f"\n  {pattern_type.title()}:")
            for name in names:
                print(f"    - {name}")

    print("\n" + "=" * 70)
    print("[COMPLETE] Analysis workflow finished!")
    print("=" * 70)
    print("\n[INSIGHTS]")
    print("  + Analysis specialists used filesystem MCP to scan code")
    print("  + Patterns were discovered through emergent agent collaboration")
    print("  + pattern_documenter aggregated findings (if BatchSpec triggered)")
    print("\n[WHAT WE LEARNED]")
    print("  + Blackboard architecture enables flexible discovery")
    print("  + Agents can analyze code and extract domain knowledge")
    print("  + MCP tools enable real file system access for analysis")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(analyze_codebase())
