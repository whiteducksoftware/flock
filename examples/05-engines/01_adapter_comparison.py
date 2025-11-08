"""
DSPy Adapter Comparison: ChatAdapter vs JSONAdapter

This example demonstrates the difference between ChatAdapter (default)
and JSONAdapter for structured output parsing reliability.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.engines import DSPyEngine
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class AnalysisRequest(BaseModel):
    text: str = Field(description="Text to analyze")


@flock_type
class AnalysisResult(BaseModel):
    sentiment: str = Field(description="Sentiment: positive, negative, or neutral")
    confidence: float = Field(description="Confidence score 0.0-1.0")
    key_points: list[str] = Field(description="Key points extracted")


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    try:
        from dspy.adapters import ChatAdapter, JSONAdapter
    except ImportError:
        print("❌ DSPy adapters not available. Install dspy>=3.0.0")
        return

    flock = Flock()

    # Agent with ChatAdapter (default)
    chat_agent = (
        flock.agent("chat_analyzer")
        .description("Analyze text using ChatAdapter (default)")
        .consumes(AnalysisRequest)
        .publishes(AnalysisResult)
        .with_engines(
            DSPyEngine(
                adapter=ChatAdapter(),  # Explicit ChatAdapter
            )
        )
    )

    # Agent with JSONAdapter (better parsing)
    json_agent = (
        flock.agent("json_analyzer")
        .description("Analyze text using JSONAdapter (structured outputs)")
        .consumes(AnalysisRequest)
        .publishes(AnalysisResult)
        .with_engines(
            DSPyEngine(
                adapter=JSONAdapter(),  # Better structured output parsing
            )
        )
    )

    request = AnalysisRequest(
        text="I love this product! It's amazing and works perfectly. The quality is outstanding and the customer service is excellent."
    )

    print("🔵 Testing ChatAdapter (default)...")
    print(f"   Input: {request.text}\n")
    await flock.publish(request, correlation_id="chat_test")
    await flock.run_until_idle()

    # Get results
    chat_results = await flock.store.get_by_type(AnalysisResult, correlation_id="chat_test")
    if chat_results:
        result = chat_results[0]
        print(f"   ✅ Sentiment: {result.sentiment}")
        print(f"   ✅ Confidence: {result.confidence:.2f}")
        print(f"   ✅ Key Points: {len(result.key_points)}")

    print("\n🟢 Testing JSONAdapter (structured outputs)...")
    print(f"   Input: {request.text}\n")
    await flock.publish(request, correlation_id="json_test")
    await flock.run_until_idle()

    # Get results
    json_results = await flock.store.get_by_type(AnalysisResult, correlation_id="json_test")
    if json_results:
        result = json_results[0]
        print(f"   ✅ Sentiment: {result.sentiment}")
        print(f"   ✅ Confidence: {result.confidence:.2f}")
        print(f"   ✅ Key Points: {len(result.key_points)}")

    print("\n✅ Both adapters completed!")
    print("\n💡 Key Differences:")
    print("   - ChatAdapter: Text-based parsing with [[ ## field_name ## ]] markers")
    print("   - JSONAdapter: Uses OpenAI's structured outputs API for more reliable parsing")
    print("   - JSONAdapter: Enables native function calling by default")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await Flock().serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)

