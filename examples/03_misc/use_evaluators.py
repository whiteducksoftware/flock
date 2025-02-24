
from flock.core import Flock, FlockFactory
from flock.core.logging.formatters.themes import OutputTheme
from flock.evaluators.zep.zep_evaluator import ZepEvaluator, ZepEvaluatorConfig



write_to_kg_agent = FlockFactory.create_default_agent(name="my_agent", 
                                          input="data", 
                                          output_theme=OutputTheme.aardvark_blue)

write_to_kg_agent.evaluator = ZepEvaluator(name="zep", config=ZepEvaluatorConfig())

result = write_to_kg_agent.run(inputs={"data": "Andre is 38 years old and author of the agent framework 'flock'"})


read_from_kg_agent = FlockFactory.create_default_agent(name="my_agent", 
                                          input="query", 
                                          output_theme=OutputTheme.aardvark_blue)

# replace the default evaluator with ZepEvaluator
read_from_kg_agent.evaluator = ZepEvaluator(name="zep", config=ZepEvaluatorConfig())

result = read_from_kg_agent.run(inputs={"query": "How old is Andre"})




