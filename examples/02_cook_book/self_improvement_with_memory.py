"""
Title: Reasoning assistant with self managed memory
"""

from datetime import datetime
import warnings

from flock.core.flock_router import HandOffRequest
from flock.core.tools import basic_tools
warnings.simplefilter("error", UserWarning)
import asyncio
from dataclasses import dataclass, field

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent, FlockAgentConfig, FlockAgentMemoryConfigt

from rich.prompt import Prompt
from rich.panel import Panel
from rich.console import Console


@dataclass
class Chat:
    chat_history: list[str] = field(default_factory=list)
    user_query: str = ""
    answer_to_query: str = ""
    memory: str = ""
    
    async def before_response(self, agent, inputs):
        console = Console()

        # Use a Rich-styled prompt to get user input
        self.user_query = Prompt.ask("[bold cyan]User[/bold cyan]")
        inputs["user_query"] = self.user_query

    # Triggers after the agent responds to the user query
    async def after_response(self, agent:FlockAgent, inputs, outputs):
        # Update answer and history based on the agent's outputs
        console = Console()
        self.answer_to_query = outputs["answer_to_query"]
        self.chat_history.append({"user": self.user_query, "assistant": self.answer_to_query})

        agent.save_memory_graph("chat_memory_graph.json")
        agent.export_memory_graph("chat_memory_graph.png")

        # Display the assistant's reasoning (if available) in a styled panel
        reasoning = outputs.get("reasoning", "")
        if reasoning:
            reasoning_panel = Panel(
                reasoning,
                title="[bold blue]Assistant Reasoning[/bold blue]",
                border_style="blue",
            )
            console.print(reasoning_panel)

        # Display the assistant's answer in a styled panel
        answer_panel = Panel(
            self.answer_to_query,
            title="[bold green]Assistant Answer[/bold green]",
            border_style="green",
        )
        console.print(answer_panel)

    # Triggers at handoff to the next agent
    def hand_off(self, context, result):
        if self.user_query.lower() == "goodbye":
            return None
        return HandOffRequest(next_agent="chatty")


MODEL = "openai/gpt-4o"

async def main():

    chat_helper = Chat()
    flock = Flock(model=MODEL, local_debug=True)

    memory_config = FlockAgentMemoryConfig()
    memory_config.storage_type = "json"
    memory_config.file_path = "chat_memory_graph.json"

    chatty = FlockAgent(
        name="chatty", 
        description=f"""You are Chatty, a friendly assistant that loves to chat. 
                    Today is {datetime.now().strftime('%A, %B %d, %Y')}.
                    """,
        input="user_query", 
        output="answer_to_query",
        initialize_callback=chat_helper.before_response,
        terminate_callback=chat_helper.after_response,
        config=FlockAgentConfig(disable_output=True),
        tools=[basic_tools.web_search_duckduckgo, 
               basic_tools.get_web_content_as_markdown, 
               basic_tools.code_eval],
        memory_enabled=True,
        memory_config=memory_config
    )
    
    flock.add_agent(chatty)

    chatty.hand_off = chat_helper.hand_off

    await flock.run_async(
        start_agent=chatty, 
        input={"user_query": ""}
    )


if __name__ == "__main__":
    asyncio.run(main())
