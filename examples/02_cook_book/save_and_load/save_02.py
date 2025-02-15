

from typing import Any, Dict, Type
from flock.core import FlockAgent
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter


# Save and load agents with custom logic

async def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    return {"result": "Hello, world!"}
    
async def on_terminate(agent,input,output):
    print(f"Agent {agent.name} has been terminated.")
    
custom_bloggy = FlockAgent(name="custom_bloggy", 
                              input="blog_idea", 
                              output="result", 
                              terminate_callback=on_terminate,
                              evaluate_callback=evaluate)
custom_bloggy.save_to_file("examples/data/custom_bloggy.json")


class MyInheritedAgent(FlockAgent):
    async def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "Hello, world!"}
    
inherited_agent = MyInheritedAgent(name="inherited_bloggy")
inherited_agent.save_to_file("examples/data/inherited_bloggy.json")

