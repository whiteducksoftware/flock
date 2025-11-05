"""
Control Routes Component Examples

This example demonstrates the ControlRoutesComponent capabilities:
1. Invoking specific agents via REST API
2. Passing input artifacts to agents
3. Controlling agent execution
4. Monitoring agent responses
"""

import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.components.server import (
    ControlRoutesComponent,
    ControlRoutesComponentConfig,
)


class AnalysisRequest(BaseModel):
    """Example artifact for analysis requests."""

    text: str
    analysis_type: str


class AnalysisResult(BaseModel):
    """Example artifact for analysis results."""

    summary: str
    key_points: list[str]
    sentiment: str


async def main():
    """Demonstrate Control Routes component usage."""
    print("🎮 Control Routes Component Examples\n")
    print("=" * 60)

    # Example 1: Basic Control Routes component
    print("\n1️⃣  Basic Control Routes Component")
    print("-" * 60)

    flock = Flock("openai/gpt-4o")

    control_component = ControlRoutesComponent(
        config=ControlRoutesComponentConfig(
            prefix="/api/v1",
            tags=["Control"],
        )
    )

    print("✅ Control Routes component created")
    print("   Endpoints:")
    print(f"   - POST {control_component.config.prefix}/agents/{{name}}/invoke")

    # Example 2: Create analyzable agent
    print("\n2️⃣  Creating Text Analyzer Agent")
    print("-" * 60)

    text_analyzer = (
        flock.agent("text_analyzer")
        .description("Analyzes text and provides insights")
        .consumes(AnalysisRequest)
        .publishes(AnalysisResult)
        .instruction(
            "Analyze the provided text and:\n"
            "1. Create a concise summary\n"
            "2. Extract 3-5 key points\n"
            "3. Determine overall sentiment (positive/negative/neutral)\n"
            "4. Provide the analysis in a structured format"
        )
    )

    print(f"✅ Agent created: {text_analyzer.name}")
    print("   Consumes: AnalysisRequest")
    print("   Publishes: AnalysisResult")

    # Example 3: Full server setup
    print("\n3️⃣  Full Server Setup")
    print("-" * 60)

    print("\n🚀 Starting server with Control Routes component...")
    print("   Server will run on http://127.0.0.1:8344")
    print("\n   Available endpoints:")
    print("   - POST http://127.0.0.1:8344/api/v1/agents/text_analyzer/invoke")
    print("\n   Press Ctrl+C to stop the server")

    # Start server (non-blocking for demo)
    await flock.serve(
        components=[control_component],
        host="127.0.0.1",
        port=8344,
        blocking=False,
    )

    # Wait for server to start
    await asyncio.sleep(2)
    print("\n✅ Server is running!")

    # Example 4: Invoke agent via API
    print("\n4️⃣  Invoking Agent via REST API")
    print("-" * 60)

    print("\n   You can now invoke the agent using curl:")
    print(
        "\n   curl -X POST http://127.0.0.1:8344/api/v1/agents/text_analyzer/invoke \\"
    )
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"artifacts": [')
    print("       {")
    print('         "type": "__main__.AnalysisRequest",')
    print('         "payload": {')
    print(
        '           "text": "This is an amazing product! I love how easy it is to use.",'
    )
    print('           "analysis_type": "sentiment"')
    print("         }")
    print("       }")
    print("     ]}'")

    print("\n   Example Python code:")
    print("""
    import requests

    response = requests.post(
        "http://127.0.0.1:8344/api/v1/agents/text_analyzer/invoke",
        json={
            "artifacts": [{
                "type": "__main__.AnalysisRequest",
                "payload": {
                    "text": "This is an amazing product!",
                    "analysis_type": "sentiment"
                }
            }]
        }
    )
    print(response.json())
    """)

    # Example 5: Test the invocation programmatically
    print("\n5️⃣  Testing Agent Invocation")
    print("-" * 60)

    # For demo purposes, we'll invoke directly
    test_request = AnalysisRequest(
        text="The new feature significantly improves user experience and productivity. "
        "However, there are some minor bugs that need to be addressed.",
        analysis_type="comprehensive",
    )

    print("\n📤 Invoking agent with test request...")
    print(f"   Text length: {len(test_request.text)} characters")
    print(f"   Analysis type: {test_request.analysis_type}")

    await flock.publish(test_request)
    await flock.run_until_idle()

    print("\n✅ Agent invocation completed!")
    print("   Check the results via the artifacts endpoint:")
    print("   curl http://127.0.0.1:8344/api/v1/artifacts?type=AnalysisResult")

    # Keep server running
    print("\n⏳ Keeping server running for 60 seconds...")
    print("   Try the curl commands above!")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
