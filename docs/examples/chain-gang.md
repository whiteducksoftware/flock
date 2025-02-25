# Chain Gang

This example demonstrates how to chain multiple agents together to create a workflow. Chaining agents allows you to break down complex tasks into smaller, more manageable steps, with each agent specializing in a specific part of the process.

## Basic Agent Chaining

Let's create a simple workflow with two agents: one that generates blog ideas and another that expands those ideas into outlines.

```python
from flock.core import Flock, FlockAgent

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# First agent: Generate blog ideas
idea_generator = FlockAgent(
    name="idea_generator",
    input="topic: str | The general topic to generate blog ideas about",
    output="blog_idea: str | A specific blog idea related to the topic"
)

# Second agent: Create outlines
outline_creator = FlockAgent(
    name="outline_creator",
    input="blog_idea: str | The blog idea to create an outline for",
    output="outline: list[str] | An outline of sections for the blog post"
)

# Chain the agents together
idea_generator.hand_off = outline_creator

# Add the agents to the flock
flock.add_agent(idea_generator)
flock.add_agent(outline_creator)

# Run the workflow
result = flock.run(
    start_agent=idea_generator,
    input={"topic": "artificial intelligence"}
)

print(result)
```

Output:
```python
{
    'topic': 'artificial intelligence',
    'blog_idea': 'The Ethical Implications of AI in Healthcare Decision-Making',
    'outline': [
        'Introduction: The Growing Role of AI in Healthcare',
        'Understanding AI-Assisted Clinical Decision Making',
        'Potential Benefits: Improved Accuracy and Efficiency',
        'Ethical Concern #1: Patient Privacy and Data Security',
        'Ethical Concern #2: Algorithmic Bias and Health Disparities',
        'Ethical Concern #3: Transparency and Explainability',
        'Ethical Concern #4: Shifting Responsibility and Liability',
        'Balancing Innovation with Ethical Considerations',
        'Regulatory Frameworks and Guidelines',
        'Conclusion: The Path Forward for Ethical AI in Healthcare'
    ]
}
```

## Multi-Agent Workflow

Let's expand our workflow to include more agents:

```python
from flock.core import Flock, FlockAgent

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# First agent: Generate blog ideas
idea_generator = FlockAgent(
    name="idea_generator",
    input="topic: str | The general topic to generate blog ideas about",
    output="blog_idea: str | A specific blog idea related to the topic"
)

# Second agent: Create outlines
outline_creator = FlockAgent(
    name="outline_creator",
    input="blog_idea: str | The blog idea to create an outline for",
    output="outline: list[str] | An outline of sections for the blog post"
)

# Third agent: Write introduction
intro_writer = FlockAgent(
    name="intro_writer",
    input="blog_idea: str | The blog idea, outline: list[str] | The blog outline",
    output="introduction: str | An engaging introduction for the blog post"
)

# Fourth agent: Generate a catchy title
title_generator = FlockAgent(
    name="title_generator",
    input="blog_idea: str | The blog idea, introduction: str | The blog introduction",
    output="title: str | A catchy title for the blog post"
)

# Chain the agents together
idea_generator.hand_off = outline_creator
outline_creator.hand_off = intro_writer
intro_writer.hand_off = title_generator

# Add the agents to the flock
flock.add_agent(idea_generator)
flock.add_agent(outline_creator)
flock.add_agent(intro_writer)
flock.add_agent(title_generator)

# Run the workflow
result = flock.run(
    start_agent=idea_generator,
    input={"topic": "machine learning"}
)

print(result)
```

## Using HandOff with Additional Input

Sometimes you want to pass additional information to the next agent in the chain. You can do this using the `HandOff` class:

```python
from flock.core import Flock, FlockAgent, HandOff

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# First agent: Generate blog ideas
idea_generator = FlockAgent(
    name="idea_generator",
    input="topic: str | The general topic to generate blog ideas about",
    output="blog_idea: str | A specific blog idea related to the topic"
)

# Second agent: Create outlines
outline_creator = FlockAgent(
    name="outline_creator",
    input="blog_idea: str | The blog idea to create an outline for, style: str | The writing style to use",
    output="outline: list[str] | An outline of sections for the blog post"
)

# Set up handoff with additional input
idea_generator.hand_off = HandOff(
    next_agent=outline_creator,
    input={"style": "conversational"}
)

# Add the agents to the flock
flock.add_agent(idea_generator)
flock.add_agent(outline_creator)

# Run the workflow
result = flock.run(
    start_agent=idea_generator,
    input={"topic": "data science"}
)

print(result)
```

## Dynamic Handoff

You can also use a function to determine the next agent dynamically based on the output of the current agent:

```python
from flock.core import Flock, FlockAgent

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# First agent: Analyze sentiment
sentiment_analyzer = FlockAgent(
    name="sentiment_analyzer",
    input="text: str | The text to analyze",
    output="sentiment: str | The sentiment of the text (positive, negative, or neutral)"
)

# Second agent: Generate positive response
positive_responder = FlockAgent(
    name="positive_responder",
    input="text: str | The original text",
    output="response: str | A response to positive text"
)

# Third agent: Generate negative response
negative_responder = FlockAgent(
    name="negative_responder",
    input="text: str | The original text",
    output="response: str | A response to negative text"
)

# Fourth agent: Generate neutral response
neutral_responder = FlockAgent(
    name="neutral_responder",
    input="text: str | The original text",
    output="response: str | A response to neutral text"
)

# Define a dynamic handoff function
def determine_next_agent(result):
    sentiment = result.get("sentiment", "").lower()
    if sentiment == "positive":
        return positive_responder
    elif sentiment == "negative":
        return negative_responder
    else:
        return neutral_responder

# Set up dynamic handoff
sentiment_analyzer.hand_off = determine_next_agent

# Add the agents to the flock
flock.add_agent(sentiment_analyzer)
flock.add_agent(positive_responder)
flock.add_agent(negative_responder)
flock.add_agent(neutral_responder)

# Run the workflow
result = flock.run(
    start_agent=sentiment_analyzer,
    input={"text": "I had a wonderful day today!"}
)

print(result)
```

## Auto Handoff

Flock also supports automatic handoff, where the LLM decides which agent to hand off to next:

```python
from flock.core import Flock, FlockAgent

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# First agent: Classify query
query_classifier = FlockAgent(
    name="query_classifier",
    input="query: str | The user's query",
    output="query_type: str | The type of query (weather, news, math, etc.)"
)

# Weather agent
weather_agent = FlockAgent(
    name="weather_agent",
    input="query: str | The user's weather-related query",
    output="weather_info: str | Weather information"
)

# News agent
news_agent = FlockAgent(
    name="news_agent",
    input="query: str | The user's news-related query",
    output="news_info: str | News information"
)

# Math agent
math_agent = FlockAgent(
    name="math_agent",
    input="query: str | The user's math-related query",
    output="math_result: str | Math calculation result"
)

# Set up auto handoff
query_classifier.hand_off = "auto_handoff"

# Add the agents to the flock
flock.add_agent(query_classifier)
flock.add_agent(weather_agent)
flock.add_agent(news_agent)
flock.add_agent(math_agent)

# Run the workflow
result = flock.run(
    start_agent=query_classifier,
    input={"query": "What's the weather like in New York?"}
)

print(result)
```

## Parallel Execution

You can also execute agents in parallel:

```python
import asyncio
from flock.core import Flock, FlockAgent

# Create a Flock instance
flock = Flock(model="openai/gpt-4o")

# Create agents
summarizer = FlockAgent(
    name="summarizer",
    input="text: str | The text to summarize",
    output="summary: str | A concise summary of the text"
)

sentiment_analyzer = FlockAgent(
    name="sentiment_analyzer",
    input="text: str | The text to analyze",
    output="sentiment: str | The sentiment of the text"
)

keyword_extractor = FlockAgent(
    name="keyword_extractor",
    input="text: str | The text to extract keywords from",
    output="keywords: list[str] | A list of keywords from the text"
)

# Add the agents to the flock
flock.add_agent(summarizer)
flock.add_agent(sentiment_analyzer)
flock.add_agent(keyword_extractor)

async def run_parallel():
    # Sample text
    text = "The new AI model has shown remarkable performance on benchmark tests, exceeding expectations and setting new standards for the industry. Researchers are excited about the potential applications in healthcare, education, and scientific discovery."
    
    # Run agents in parallel
    summary_task = flock.run_async(
        start_agent=summarizer,
        input={"text": text}
    )
    
    sentiment_task = flock.run_async(
        start_agent=sentiment_analyzer,
        input={"text": text}
    )
    
    keyword_task = flock.run_async(
        start_agent=keyword_extractor,
        input={"text": text}
    )
    
    # Gather results
    summary_result, sentiment_result, keyword_result = await asyncio.gather(
        summary_task, sentiment_task, keyword_task
    )
    
    # Combine results
    combined_result = {
        "summary": summary_result["summary"],
        "sentiment": sentiment_result["sentiment"],
        "keywords": keyword_result["keywords"]
    }
    
    return combined_result

# Run the parallel execution
result = asyncio.run(run_parallel())
print(result)
```

## Best Practices for Agent Chaining

1. **Single Responsibility**: Each agent should have a single, well-defined responsibility.
2. **Clear Interfaces**: Define clear input and output schemas for each agent.
3. **Error Handling**: Consider how errors will be handled in your workflow.
4. **Testing**: Test each agent individually before chaining them together.
5. **Monitoring**: Monitor the performance of your workflow in production.
6. **Fallbacks**: Implement fallback mechanisms for when agents fail.
7. **Documentation**: Document the purpose and behavior of each agent in the chain.

## Next Steps

Now that you've learned about agent chaining, you might want to explore:

- [Custom Agents](../advanced/custom-agents.md) - Learn how to create custom agent implementations
- [Complex Workflows](../advanced/complex-workflows.md) - Learn about more complex workflow patterns
- [Routers](../core-concepts/routers.md) - Learn about the routing system in Flock
- [Temporal Integration](../integrations/temporal.md) - Learn about using Temporal for workflow orchestration
