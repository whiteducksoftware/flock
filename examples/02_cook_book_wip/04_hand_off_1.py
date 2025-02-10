import asyncio

from devtools import debug


from flock.agents.batch_agent import BatchAgent

from flock.core.flock_agent import FlockAgent, HandoffBase
from flock.core.context.context import FlockContext
from flock.core.flock import Flock
from flock.core.tools import basic_tools

MODEL = "openai/gpt-4o"

collected_research = ""
queries = ["research the latest trends in AI"]

def handoff_to_content_agent(context: FlockContext) -> HandoffBase:
    global collected_research
    collected_research += context.output
    if(len(collected_research) > 5000):
        return None
    
    new_query_to_research = context.get_variable("query_agent.new_query_to_research")

    # Overriding the parameters of the next agent
    # "Agents are not about little James Bonds, but about being able to 'program' an LLM."
    return HandoffBase(
        next_agent="content_agent",
        input={"new_query": new_query_to_research,
               "collected_research": collected_research,
               "prev_queries": context.get_variable("query_agent.prev_queries")},
        context=context,
    )

async def main():
    flock = Flock(local_debug=True)

    content_agent = FlockAgent(
        name="content_agent",
        input="user_query",
        output="research_result",
        tools=[basic_tools.web_search_tavily]
        
    )
    

    query_agent = DeclarativeAgent(
        name="query_agent",
        input="research_results",
        output="new_query_to_research",
    )

    flock.add_agent(content_agent)
    flock.add_agent(query_agent)

    content_agent.hand_off = query_agent
    query_agent.hand_off = handoff_to_content_agent

    await flock.run_async(
        start_agent=content_agent,
        input=queries[0],
        local_debug=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
