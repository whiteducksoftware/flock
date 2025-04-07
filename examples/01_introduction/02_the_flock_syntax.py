import os
from flock.core import Flock, FlockFactory 



MODEL = "openai/gpt-4o"



flock = Flock(name="example_02", description="The flock input and output syntax", model=MODEL)

# Obviously the input and output define what flock can do.
# The description is not used only for documentation, but also to control the behavior of the agent.
# General syntax rules:
# "field_name: type | description"
presentation_agent = FlockFactory.create_default_agent(
    name="my_presentation_agent",
    description="Creates a fun presentation about a given topic",
    input="topic: str, number_of_slides: int",
    output="fun_title: str | The funny title of the presentation in all caps, "
    "fun_subtitle: str | A funny subtitle for the presentation, "  
    "fun_slides: dict[int, tuple[str, list[str]]] | Key is slide number - Value are header and at least 5 bullet points, " 
)
flock.add_agent(presentation_agent)



flock.run(
    start_agent=presentation_agent, 
    input={"topic": "AI agents", "number_of_slides": 5}
)

# YOUR TURN!
# Try changing the output definition (line 30) by replacing "fun" with "boring" 
# (boring_title, boring_slide_headers, boring_slide_summaries)

