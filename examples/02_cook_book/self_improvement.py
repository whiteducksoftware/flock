"""
Title: Reasoning assistant with self managed memory
"""

from datetime import datetime
import warnings

from flock.core.tools import basic_tools
warnings.simplefilter("error", UserWarning)
import asyncio
from dataclasses import dataclass, field

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent, FlockAgentConfig, HandOff

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
        # Load the memory from file (if it exists)
        try:
            with open("memory.txt", "r") as file:
                self.memory = file.read()
        except FileNotFoundError:
            self.memory = ""

        # Use a Rich-styled prompt to get user input
        self.user_query = Prompt.ask("[bold cyan]User[/bold cyan]")
        inputs["user_query"] = self.user_query
        inputs["chat_history"] = self.chat_history
        inputs["memory"] = self.memory

    # Triggers after the agent responds to the user query
    async def after_response(self, agent, inputs, outputs):
        # Update answer and history based on the agent's outputs
        console = Console()
        self.answer_to_query = outputs["answer_to_query"]
        self.chat_history.append({"user": self.user_query, "assistant": self.answer_to_query})
        self.memory += outputs.get("important_new_knowledge_to_add_to_memory", "") + "\n"

        # Save updated memory to file
        with open("memory.txt", "w") as file:
            file.write(self.memory)

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
        return HandOff(next_agent="chatty")
    
    
def optimize_memory(optimized_memory:str):
    try:
        with open("memory.txt", "w") as file:
            file.write(optimized_memory)
    except FileNotFoundError:
        pass


MODEL = "openai/gpt-4o"

async def main():

    chat_helper = Chat()
    flock = Flock(model=MODEL, local_debug=True)


    chatty = FlockAgent(
        name="chatty", 
        description=f"""You are Chatty, a friendly assistant that loves to chat. 
                    Today is {datetime.now().strftime('%A, %B %d, %Y')}.
                    Use web_search_duckduckgo to search the web, 
                    +get_web_content_as_markdown to get web content as markdown, 
                    and code_eval for all tasks that require code execution.
                    Save knowledge to memory for future reference.
                    Once in a while optimize your knowledge by calling the optimize_memory tool 
                    with the optimized memory as input.
                    """,
        input="user_query, memory | Memory of previous interactions, chat_history | the current chat history", 
        output="answer_to_query, important_new_knowledge_to_add_to_memory | Empty string if no knowledge to add",
        initialize_callback=chat_helper.before_response,
        terminate_callback=chat_helper.after_response,
        config=FlockAgentConfig(disable_output=True),
        tools=[basic_tools.web_search_duckduckgo, 
               basic_tools.get_web_content_as_markdown, 
               basic_tools.code_eval,optimize_memory],
    )
    
    flock.add_agent(chatty)

    chatty.hand_off = chat_helper.hand_off

    await flock.run_async(
        start_agent=chatty, 
        input={"memory": "","user_query": "","chat_history": ""}
    )


if __name__ == "__main__":
    asyncio.run(main())
