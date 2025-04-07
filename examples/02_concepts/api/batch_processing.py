from flock.core import Flock, FlockFactory
from flock.core.api import runner 


MODEL = "openai/gpt-4o"


flock = Flock(name="batch_rest_api", description="Shows how to use the batch processing API", model=MODEL)

presentation_agent = FlockFactory.create_default_agent(
    name="my_presentation_agent",
    input="topic, audience, number_of_slides",
    output="fun_title, fun_slide_headers, fun_slide_summaries",
    use_cache=False
)
flock.add_agent(presentation_agent)


runner.start_flock_api(flock)
