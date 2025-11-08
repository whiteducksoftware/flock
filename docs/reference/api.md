import dspy
from flock.engines import DSPyEngine
from dspy.adapters import JSONAdapter, ChatAdapter

# Example 1: Basic DSPyEngine with default adapter (implicitly ChatAdapter for most models)
# This will generally result in unstructured text outputs.
openai_lm = dspy.OpenAI(model="gpt-4o", api_key="YOUR_OPENAI_API_KEY")
basic_dspy_engine = DSPyEngine(lm=openai_lm)

# Example 2: DSPyEngine configured with JSONAdapter for structured outputs
# Ideal for scenarios where the agent needs to produce or consume JSON data.
json_adapter = JSONAdapter()
structured_dspy_engine = DSPyEngine(lm=openai_lm, adapter=json_adapter)

# Example 3: DSPyEngine explicitly configured with ChatAdapter
# Useful if you specifically want to ensure a pure chat-like interaction without structured output enforcement.
chat_adapter = ChatAdapter()
chat_dspy_engine = DSPyEngine(lm=openai_lm, adapter=chat_adapter)