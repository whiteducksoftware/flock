
from flock.core import Flock, FlockFactory
from flock.core.logging.formatters.themes import OutputTheme
from flock.evaluators.zep.zep_evaluator import ZepEvaluator, ZepEvaluatorConfig
from flock.modules.zep.zep_module import ZepModule, ZepModuleConfig


def write_to_kg():
  write_to_kg_agent = FlockFactory.create_default_agent(name="write_to_kg_agent", 
                                            input="data", 
                                            output_theme=OutputTheme.aardvark_blue)
  
  # --------------------------------
  # Evaluators
  # --------------------------------
  # Evaluators are the components that evaluate the agent's inputs and outputs.
  # In this case, we're using the ZepEvaluator to interact with Zep.
  # This replaces the default declarative evaluator
  # The ZepEvaluator uses the ZepModule to interact with Zep.
  # input with "data" will add the data to the memory
  # input with "query" will search the memory for the query and return the facts
  write_to_kg_agent.evaluator = ZepEvaluator(name="zep", config=ZepEvaluatorConfig())

  write_to_kg_agent.run(inputs={"data": "Andre is 38 years old and author of the agent framework 'flock'"})
  write_to_kg_agent.run(inputs={"data": "Andre works for white duck"})
  write_to_kg_agent.run(inputs={"data": "Andre has two cats"})
  write_to_kg_agent.run(inputs={"data": "White Duck is a cloud consulting company"})
  write_to_kg_agent.run(inputs={"data": "Flock is an agent framework designed for scalable multi-agent systems"})
  write_to_kg_agent.run(inputs={"data": "One of Andre's cats is named Luna"})
  write_to_kg_agent.run(inputs={"data": "The other cat is named Lucy"})
  write_to_kg_agent.run(inputs={"data": "Andre lives in Germany"})
  write_to_kg_agent.run(inputs={"data": "Germany is in Europe"})

def read_from_kg():
  read_from_kg_agent = FlockFactory.create_default_agent(name="read_from_kg_agent", 
                                            input="query", 
                                            output_theme=OutputTheme.aardvark_blue)

  # replace the default evaluator with ZepEvaluator
  read_from_kg_agent.evaluator = ZepEvaluator(name="zep", config=ZepEvaluatorConfig())


  # #### **2-Hop Question:**
  # **Question:** What kind of company does the employer of the author of 'flock' belong to?  
  # **Reasoning:**  
  # 1. "Andre is the author of the agent framework 'flock'."  
  # 2. "Andre works for White Duck."  
  # 3. "White Duck is a cloud consulting company."  
  # 4. Therefore, the employer of the author of 'flock' is a cloud consulting company.

  read_from_kg_agent.run(inputs={"query": "What kind of company does the employer of the author of 'flock' belong to?"})

def read_from_kg_and_evaluate():
  read_from_kg_and_evaluate_agent = FlockFactory.create_default_agent(name="read_from_kg_and_evaluate_agent", 
                                            input="query", 
                                            output="short_answer",
                                            output_theme=OutputTheme.aardvark_blue)
  
  read_from_kg_and_evaluate_agent.add_module(ZepModule(name="zep", config=ZepModuleConfig()))



  read_from_kg_and_evaluate_agent.run(inputs={"query": "What kind of company does the employer of the author of 'flock' belong to?"})

  # #### **3-Hop Question:**
  # **Question:** In which continent does the creator of the agent framework 'flock' live?  
  # **Reasoning:**  
  # 1. "Andre is the author of the agent framework 'flock'."  
  # 2. "Andre lives in Germany."  
  # 3. "Germany is in Europe."  
  # 4. Therefore, the creator of 'flock' lives in Europe.
  read_from_kg_and_evaluate_agent.run(inputs={"query": "In which continent does the creator of the agent framework 'flock' live? "})



if __name__ == "__main__":
  #write_to_kg()
  read_from_kg()
  #read_from_kg_and_evaluate()
  pass





