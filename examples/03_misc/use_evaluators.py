
from flock.core import Flock, FlockFactory
from flock.core.logging.formatters.themes import OutputTheme
from flock.evaluators.zep.zep_evaluator import ZepEvaluator, ZepEvaluatorConfig

flock = Flock()


agent = FlockFactory.create_default_agent(name="my_agent", 
                                          input="query", 
                                          output_theme=OutputTheme.aardvark_blue)

# replace the default evaluator with ZepEvaluator
agent.evaluator = ZepEvaluator(name="zep", config=ZepEvaluatorConfig())


flock.add_agent(agent)


flock.run(start_agent=agent, input={"query": "What did Alexander the Great do?"})

