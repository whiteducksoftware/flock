import asyncio

from devtools import debug



from flock.agents.user_agent import UserAgent
from flock.core.flock_agent import FlockAgent, HandoffBase
from flock.core.context.context import FlockContext
from flock.core.flock import Flock

from flock.core.tools import basic_tools

MODEL = "openai/gpt-4o"


def hand_off_to_chat_agent_with_history(context: FlockContext, agent: UserAgent) -> HandoffBase:
    """Hand off to the chat agent with the historical messages."""
    if "historical_messages" in context.state:
        context.state["historical_messages"].append(agent.message_history)
    else:
        context.state["historical_messages"] = [agent.message_history]
    return HandoffBase(next_agent="my_chat_agent", input="", context=context)


async def main():
    flock, _ = Flock.create()

    chat_agent = FlockAgent(
        name="my_chat_agent",
        input="user_message,historical_messages",
        output="helpful_assistant_answer",
        tools=[basic_tools.web_search_tavily, basic_tools.code_eval],
    )
    flock.add_agent(chat_agent)

    user_agent = UserAgent(
        name="user",
        input="helpful_assistant_answer",
        output="user_message",
        termination="bye",
    )

    user_agent.hand_off = hand_off_to_chat_agent_with_history()
    chat_agent.hand_off = user_agent

    result = await flock.run_async(
        local_debug=True,
        start_agent=chat_agent,
        input="Johnny Depp",
    )
    debug(result)


if __name__ == "__main__":
    asyncio.run(main())
