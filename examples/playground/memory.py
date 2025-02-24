
from flock.core import Flock, FlockAgent
from flock.core.tools import basic_tools
from uuid import uuid4

# Initialize Flock with memory
flock = Flock(
    model="openai/gpt-4",
    memory_config={
        "use_global": True,  # Enable global memory
        "global_weight": 0.4,  # Weight for global knowledge
        "local_weight": 0.6   # Weight for specialized knowledge
    }
)

# 1. Research Agent: Gathers and analyzes information
researcher = FlockAgent(
    name="researcher",
    input="""
        topic: str | The research topic,
        depth: str | Research depth (quick/thorough/comprehensive),
        context: str | Additional context or requirements
    """,
    output="""
        findings: list[dict] | Key research findings,
        sources: list[dict] | Sources and citations,
        analysis: str | Initial analysis and insights
    """,
    tools=[
        basic_tools.web_search_tavily,
        basic_tools.web_search_duckduckgo,
        basic_tools.get_web_content_as_markdown,
        basic_tools.extract_urls,
        basic_tools.extract_numbers,
    ],
    memory_mapping="""
        # Check if we've researched this before
        topic -> memory.semantic(threshold=0.85, scope='local') |
        memory.filter(recency='30d') -> recent_research |

        # Get global knowledge
        topic -> memory.semantic(scope='global') |
        memory.spread(depth=2) |  # Find related topics
        memory.filter(relevance=0.7) -> background |

        # Combine and enrich with fresh research
        memory.combine(
            weights={'recent': 0.6, 'background': 0.4}
        ) |
        memory.enrich(
            tools=['web_search_tavily', 'web_search_duckduckgo'],
            strategy='comprehensive'
        ) |
        memory.sort(by='relevance')
        -> findings, sources, analysis
    """
)

# 2. Analyst: Processes research and identifies patterns
analyst = FlockAgent(
    name="analyst",
    input="""
        findings: list[dict] | Research findings to analyze,
        analysis_type: str | Type of analysis needed,
        focus_areas: list[str] | Specific areas to focus on
    """,
    output="""
        patterns: list[dict] | Identified patterns and trends,
        insights: list[dict] | Key insights and implications,
        recommendations: list[str] | Actionable recommendations
    """,
    tools=[
        basic_tools.evaluate_math,
        basic_tools.extract_numbers,
        basic_tools.json_parse_safe,
    ],
    memory_mapping="""
        # Check for similar analyses
        findings -> memory.semantic(scope='local') |
        memory.filter(
            metadata={'type': 'analysis'},
            recency='90d'
        ) -> previous_analyses |

        # Get global patterns
        findings -> memory.semantic(scope='global') |
        memory.concepts |
        memory.spread(depth=3) -> global_patterns |

        # Combine and process
        memory.combine(
            weights={'previous': 0.4, 'global': 0.6}
        ) |
        memory.enrich(
            tools=['evaluate_math', 'extract_numbers'],
            strategy='validated'
        ) |
        memory.store(
            scope='both',
            metadata={'type': 'analysis_pattern'}
        ) -> patterns, insights, recommendations
    """
)

# 3. Content Creator: Produces tailored content
writer = FlockAgent(
    name="writer",
    input="""
        patterns: list[dict] | Patterns to write about,
        insights: list[dict] | Key insights to cover,
        audience: str | Target audience,
        style: str | Writing style,
        format: str | Content format
    """,
    output="""
        title: str | Content title,
        content: str | Main content,
        summary: str | Executive summary,
        sections: list[dict] | Content sections
    """,
    tools=[
        basic_tools.count_words,
        basic_tools.get_current_time,
    ],
    memory_mapping="""
        # Check writing patterns
        audience, style -> memory.exact(scope='local') |
        memory.sort(by='access_count') -> style_patterns |

        # Get relevant content examples
        patterns, insights -> memory.semantic(scope='global') |
        memory.filter(
            metadata={'format': format},
            relevance=0.8
        ) -> content_examples |

        # Combine and create
        memory.combine(
            weights={'style': 0.4, 'content': 0.6}
        ) |
        memory.enrich(
            tools=['count_words'],
            metadata={'word_count': 'total'}
        ) |
        memory.store(
            scope='both',
            metadata={'type': 'content', 'format': format}
        ) -> title, content, summary, sections
    """
)

# 4. Quality Checker: Ensures quality and consistency
checker = FlockAgent(
    name="checker",
    input="""
        content: dict | Content to check,
        standards: list[str] | Quality standards to apply,
        previous_feedback: list[dict] | Previous revision feedback
    """,
    output="""
        issues: list[dict] | Identified issues,
        suggestions: list[dict] | Improvement suggestions,
        quality_score: float | Overall quality score
    """,
    tools=[
        basic_tools.web_search_tavily,
        basic_tools.extract_urls,
    ],
    memory_mapping="""
        # Check against quality patterns
        content -> memory.semantic(scope='global') |
        memory.filter(
            metadata={'type': 'quality_check'},
            threshold=0.9
        ) -> quality_patterns |

        # Get relevant feedback
        content -> memory.semantic(scope='local') |
        memory.filter(
            metadata={'type': 'feedback'},
            recency='180d'
        ) -> historical_feedback |

        # Combine and validate
        memory.combine(weights={'quality': 0.7, 'feedback': 0.3}) |
        memory.enrich(
            tools=['web_search_tavily'],
            strategy='validated'
        ) |
        memory.store(
            scope='both',
            metadata={'type': 'quality_check'}
        ) -> issues, suggestions, quality_score
    """
)

# Set up the workflow
researcher.hand_off = analyst
analyst.hand_off = writer
writer.hand_off = checker

# Add all agents to flock
flock.add_agent(researcher)
flock.add_agent(analyst)
flock.add_agent(writer)
flock.add_agent(checker)

# Example usage
async def main():
    result = await flock.run_async(
        start_agent=researcher,
        input={
            "topic": "Recent breakthroughs in quantum computing",
            "depth": "comprehensive",
            "context": "Focus on practical applications",
            "analysis_type": "trend_analysis",
            "focus_areas": ["business impact", "timeline", "technical feasibility"],
            "audience": "business executives",
            "style": "professional",
            "format": "executive_brief",
            "standards": [
                "technical accuracy",
                "business relevance",
                "clarity",
                "actionable insights"
            ]
        }
    )
    return result

if __name__ == "__main__":
    import asyncio
    result = asyncio.run(main())


# This system:

# 1. **Builds Knowledge Over Time**:
#    - Remembers past research and analyses
#    - Learns writing patterns that work well
#    - Accumulates quality standards

# 2. **Uses Memory Effectively**:
#    - Global memory for shared knowledge
#    - Local memory for specialized patterns
#    - Concept spreading for related topics

# 3. **Leverages Tools**:
#    - Web search for fresh data
#    - Data extraction and validation
#    - Content analysis tools

# 4. **Gets Smarter With Use**:
#    - Writing styles adapt to audience feedback
#    - Quality checks learn from past issues
#    - Research patterns improve over time

# Would you like me to:
# 1. Add more specific memory operations?
# 2. Show how to analyze the memory state?
# 3. Add error handling and recovery?