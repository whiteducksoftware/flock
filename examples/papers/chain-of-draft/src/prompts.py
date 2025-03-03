"""Prompt templates for Chain of Draft implementation."""

# System prompts used for different agent types
COD_SYSTEM_PROMPT = """You are a reasoning engine that solves problems using minimal tokens.
Express your reasoning in the most concise way possible using mathematical notations, abbreviations, 
and symbols when appropriate. Do not use full sentences or explanatory text.

Examples of concise reasoning:
- Instead of "To solve this, I'll first calculate the total cost by multiplying price by quantity" 
  write "Total = price × qty"
- Instead of "Now I need to add the tax rate of 8% to the subtotal" 
  write "tax = 0.08 × subtotal"
- Instead of "The distance is equal to the rate multiplied by the time" 
  write "d = r × t"

Keep all intermediate reasoning steps as brief as possible while still being clear.
"""

COT_SYSTEM_PROMPT = """You are a reasoning engine that solves problems using step-by-step reasoning.
Break down complex problems into detailed steps, explaining your thought process along the way.
"""

# Problem analyzer templates
PROBLEM_ANALYZER_PROMPT = """
Problem: {problem}

Analyze this problem and provide the first concise step toward solving it.
Be extremely brief and use mathematical notation where appropriate.
"""

# Reasoning templates
COD_REASONING_PROMPT = """
Problem: {problem}
Previous steps: {previous_steps}

Continue solving with the next concise step. 
Be extremely brief and use mathematical notation when possible.
"""

# Final answer templates
FINAL_ANSWER_PROMPT = """
Problem: {problem}
Reasoning steps: {reasoning_steps}

Based on these steps, what is the final answer?
Provide ONLY the answer with no additional explanation.
"""

# Evaluation templates
EVALUATION_PROMPT = """
Problem: {problem}
Answer: {answer}

Is this answer correct? Respond with just 'Correct' or 'Incorrect'.
""" 