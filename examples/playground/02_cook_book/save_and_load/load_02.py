from typing import Any, Dict
from flock.core import FlockAgent
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter

# Load agents with custom logic - Everything passed to the constructor is loaded
custom_bloggy = FlockAgent.load_from_file("examples/data/custom_bloggy.json")

result = custom_bloggy.run(inputs={"blog_idea": "Idea for a blog post."})
PrettyPrintFormatter().display_data(result)

# Inherited FlockAgents have to load from their own class
# so that the custom logic is loaded as well.
# this won't work:
inherited_agent = FlockAgent.load_from_file("examples/data/inherited_bloggy.json")

result = inherited_agent.run(inputs={"blog_idea": "This will fail"})
PrettyPrintFormatter().display_data(result)

# this will work:
class MyInheritedAgent(FlockAgent):
    async def evaluate(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "Hello, world!"}

inherited_agent = MyInheritedAgent.load_from_file("examples/data/inherited_bloggy.json")

result = inherited_agent.run(inputs={"blog_idea": "Idea for a blog post."})
PrettyPrintFormatter().display_data(result)