"""
Hackathon Track 08: Custom Engines and Components

🎓 LEARNING OBJECTIVE:
Learn how to extend Flock with custom processing logic.
Engines define HOW agents process data, components add cross-cutting behavior.

KEY CONCEPTS:
- Custom EngineComponent for processing logic
- Custom AgentComponent for lifecycle hooks
- When to use engines vs components
- Extending Flock's capabilities

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from collections import Counter

from pydantic import BaseModel, Field

from flock import Flock, flock_type
from flock.components import AgentComponent, EngineComponent
from flock.runtime import EvalInputs, EvalResult


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# STEP 1: Define Types
# ============================================================================

@flock_type
class TextInput(BaseModel):
    """Input text to analyze."""
    text: str = Field(description="Text to analyze")
    language: str = Field(default="en", description="Language code")


@flock_type
class SentimentAnalysis(BaseModel):
    """Sentiment analysis results."""
    text: str
    sentiment: str = Field(description="Sentiment: positive, negative, or neutral")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    keywords: list[str] = Field(description="Key words that influenced sentiment")
    word_count: int


# ============================================================================
# STEP 2: Create Custom Engine
# ============================================================================
# Engines define HOW agents process data.
# They replace the default LLM-based processing with your own logic.
#
# Use engines when:
# - You need deterministic processing (rules, algorithms)
# - You want to avoid LLM costs
# - You have domain-specific logic
# - You need high performance
# ============================================================================

class SimpleSentimentEngine(EngineComponent):
    """A simple rule-based sentiment analyzer.
    
    This engine uses keyword matching instead of LLM calls.
    Perfect for when you need fast, deterministic sentiment analysis.
    """
    
    # Define sentiment keywords
    POSITIVE_WORDS = {
        "good", "great", "excellent", "amazing", "wonderful", "fantastic",
        "love", "happy", "pleased", "satisfied", "perfect", "best"
    }
    
    NEGATIVE_WORDS = {
        "bad", "terrible", "awful", "horrible", "hate", "disappointed",
        "worst", "poor", "fail", "broken", "useless", "waste"
    }
    
    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        """Process input and generate sentiment analysis."""
        # Get the input artifact
        text_input = inputs.first_as(TextInput)
        if not text_input:
            return EvalResult.empty()
        
        # Analyze sentiment using keyword matching
        words = set(word.lower().strip(".,!?") for word in text_input.text.split())
        
        positive_count = len(words & self.POSITIVE_WORDS)
        negative_count = len(words & self.NEGATIVE_WORDS)
        
        # Determine sentiment
        if positive_count > negative_count:
            sentiment = "positive"
            confidence = min(0.9, 0.5 + (positive_count * 0.1))
            keywords = list(words & self.POSITIVE_WORDS)
        elif negative_count > positive_count:
            sentiment = "negative"
            confidence = min(0.9, 0.5 + (negative_count * 0.1))
            keywords = list(words & self.NEGATIVE_WORDS)
        else:
            sentiment = "neutral"
            confidence = 0.5
            keywords = []
        
        # Create output artifact
        result = SentimentAnalysis(
            text=text_input.text,
            sentiment=sentiment,
            confidence=confidence,
            keywords=keywords[:5],  # Top 5 keywords
            word_count=len(text_input.text.split())
        )
        
        return EvalResult.from_object(result, agent=agent)


# ============================================================================
# STEP 3: Create Custom Component
# ============================================================================
# Components add cross-cutting behavior via lifecycle hooks.
# They don't process data directly, but modify behavior around processing.
#
# Use components when:
# - You need to modify inputs before processing
# - You want to log, track, or monitor execution
# - You need to add validation or filtering
# - You want to modify outputs after processing
# ============================================================================

class SentimentLogger(AgentComponent):
    """Logs sentiment analysis results for monitoring.
    
    This component hooks into the agent lifecycle to log results.
    It doesn't change processing logic, just adds observability.
    """
    
    log_count: int = Field(default=0, description="Number of analyses logged")
    
    async def on_post_evaluate(self, agent, ctx, inputs: EvalInputs, result: EvalResult):
        """Called after agent processes input."""
        if result.has_output:
            # Extract sentiment from result
            output_data = result.output_value
            if isinstance(output_data, dict) and "sentiment" in output_data:
                sentiment = output_data["sentiment"]
                confidence = output_data.get("confidence", 0.0)
                
                self.log_count += 1
                print(f"   📊 [Logger] Analysis #{self.log_count}: "
                      f"{sentiment} (confidence: {confidence:.2f})")
        
        return result


# ============================================================================
# STEP 4: Create the Orchestrator and Agent
# ============================================================================

flock = Flock()

# Create agent with custom engine and component
sentiment_analyzer = (
    flock.agent("sentiment_analyzer")
    .description("Analyzes text sentiment using rule-based engine")
    .consumes(TextInput)
    .publishes(SentimentAnalysis)
    .with_engines(SimpleSentimentEngine())  # Use custom engine
    .with_utilities(SentimentLogger())        # Add logging component
)


# ============================================================================
# STEP 5: Run and Observe Custom Processing
# ============================================================================

async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    print("=" * 70)
    print("⚙️  CUSTOM ENGINES EXAMPLE - Rule-Based Sentiment Analysis")
    print("=" * 70)
    print()
    
    # Test with various texts
    texts = [
        TextInput(text="This product is amazing! I love it so much.", language="en"),
        TextInput(text="Terrible service, worst experience ever.", language="en"),
        TextInput(text="The weather is okay today, nothing special.", language="en"),
        TextInput(text="Fantastic quality and excellent customer support!", language="en"),
    ]
    
    print("📝 Analyzing Texts:")
    for i, text_input in enumerate(texts, 1):
        print(f"   {i}. {text_input.text}")
    print()
    print("⏳ Processing with custom sentiment engine...")
    print("   (No LLM calls - using rule-based logic!)")
    print()
    
    # Publish all texts
    await flock.publish_many(texts)
    
    # Run until completion
    await flock.run_until_idle()
    
    # Retrieve results
    analyses = await flock.store.get_by_type(SentimentAnalysis)
    
    print("=" * 70)
    print("📊 SENTIMENT ANALYSIS RESULTS")
    print("=" * 70)
    print()
    
    for analysis in analyses:
        sentiment_emoji = {
            "positive": "😊",
            "negative": "😞",
            "neutral": "😐"
        }.get(analysis.sentiment, "❓")
        
        print(f"{sentiment_emoji} {analysis.sentiment.upper()} "
              f"(confidence: {analysis.confidence:.2f})")
        print(f"   Text: {analysis.text[:60]}...")
        if analysis.keywords:
            print(f"   Keywords: {', '.join(analysis.keywords)}")
        print(f"   Word count: {analysis.word_count}")
        print()
    
    print("=" * 70)
    print("💡 Key Insights:")
    print("   - Custom engine processes without LLM calls")
    print("   - Component adds logging without changing logic")
    print("   - Fast, deterministic, and cost-effective!")
    print("   - Easy to extend with more sophisticated logic")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    print("🌐 Starting Flock Dashboard...")
    print("   Visit http://localhost:8344 to see custom engine in action!")
    print()
    print("💡 Watch how the custom engine processes without LLM calls!")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# 🎓 NOW IT'S YOUR TURN!
# ============================================================================
# 
# EXPERIMENT 1: Improve the Sentiment Engine
# -------------------------------------------
# Enhance SimpleSentimentEngine:
#   - Add more positive/negative words
#   - Handle negations ("not good" = negative)
#   - Consider word intensity ("very good" vs "good")
#   - Add emoji detection
#
# How does accuracy improve?
#
#
# EXPERIMENT 2: Create a Different Engine
# ----------------------------------------
# Build a new engine for a different task:
#   class KeywordExtractorEngine(EngineComponent):
#       async def evaluate(self, agent, ctx, inputs, output_group):
#           # Extract keywords from text
#           # Use TF-IDF or simple frequency counting
#           pass
#
# What domain-specific engines can you create?
#
#
# EXPERIMENT 3: Add More Component Hooks
# ---------------------------------------
# Extend SentimentLogger to use other hooks:
#   async def on_pre_evaluate(self, agent, ctx, inputs):
#       # Log before processing
#       print(f"Processing: {inputs.artifacts[0].payload['text']}")
#       return inputs
#
#   async def on_post_publish(self, agent, ctx, outputs):
#       # Log after publishing
#       print(f"Published {len(outputs)} artifacts")
#
# What other hooks are available? Check AgentComponent base class!
#
#
# EXPERIMENT 4: Component for Input Validation
# ----------------------------------------------
# Create a validation component:
#   class TextValidator(AgentComponent):
#       async def on_pre_evaluate(self, agent, ctx, inputs):
#           text_input = inputs.first_as(TextInput)
#           if text_input and len(text_input.text) < 10:
#               raise ValueError("Text too short!")
#           return inputs
#
# What happens if validation fails?
#
#
# EXPERIMENT 5: Component for Output Filtering
# ----------------------------------------------
# Create a component that filters outputs:
#   class ConfidenceFilter(AgentComponent):
#       min_confidence: float = 0.7
#
#       async def on_post_evaluate(self, agent, ctx, inputs, result):
#           if result.has_output:
#               data = result.output_value
#               if data.get("confidence", 0) < self.min_confidence:
#                   return EvalResult.empty()  # Filter out low confidence
#           return result
#
# How does this affect outputs?
#
#
# EXPERIMENT 6: Hybrid Approach
# ------------------------------
# Combine custom engine with LLM:
#   class HybridEngine(EngineComponent):
#       async def evaluate(self, agent, ctx, inputs, output_group):
#           # First, try rule-based approach
#           rule_result = self._rule_based_analysis(inputs)
#           
#           # If confidence low, use LLM
#           if rule_result.confidence < 0.6:
#               return await self._llm_analysis(agent, ctx, inputs)
#           
#           return rule_result
#
# When would this be useful?
#
#
# EXPERIMENT 7: Component for Metrics
# ------------------------------------
# Create a metrics component:
#   class MetricsCollector(AgentComponent):
#       processing_times: list[float] = Field(default_factory=list)
#       success_count: int = 0
#       error_count: int = 0
#
#       async def on_post_evaluate(self, agent, ctx, inputs, result):
#           # Track metrics
#           if result.has_output:
#               self.success_count += 1
#           else:
#               self.error_count += 1
#
# How can you use this for monitoring?
#
#
# CHALLENGE: Build a Complete Custom System
# -------------------------------------------
# Design a domain-specific system with:
#   1. Custom engine for domain logic (e.g., code quality analyzer, 
#      image classifier, data validator)
#   2. Component for input validation
#   3. Component for output filtering
#   4. Component for metrics collection
#   5. Component for logging/auditing
#
# Examples:
#   - Code review system (syntax checker engine + quality gates component)
#   - Data pipeline (ETL engine + validation component)
#   - Content moderation (rule-based engine + logging component)
#
# What domain interests you? Build it!
#
# ============================================================================

