

from typing import Any, Dict, Type
from flock.core import FlockAgent
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter


# Save and load agents

bloggy = FlockAgent(name="bloggy", input="blog_idea", output="funny_blog_title, blog_headers") 
bloggy.save_to_file()


not_bloggy = FlockAgent.load_from_file("bloggy.cloudpickle")
result = not_bloggy.run(inputs={"blog_idea": "A blog about cats"})
PrettyPrintFormatter().display_data(result)


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
custom_bloggy.save_to_file()


not_bloggy = FlockAgent.load_from_file("custom_bloggy.cloudpickle")
result = not_bloggy.run(inputs={"blog_idea": "A blog about cats"})
PrettyPrintFormatter().display_data(result)


# Even if the agent is not the same class, it will still work
# override methods > callbacks, so it won't print "Hello, world!"
# but the on_terminate callback will still work
class MyCustomAgent2(FlockAgent):
    async def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "Different result!"}


not_custom_bloggy = MyCustomAgent2.load_from_file("custom_bloggy.cloudpickle")
result = not_custom_bloggy.run(inputs={"blog_idea": "A blog about cats"})
PrettyPrintFormatter().display_data(result)

