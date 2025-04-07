import random
from flock.core.flock import Flock
from flock.core.flock_factory import FlockFactory
from flock.core.flock_registry import flock_tool

### define tools for flock

@flock_tool
def get_specials():
  "Provides a list of specials from the menu."
  return """
        Special Soup: Clam Chowder
        Special Salad: Cobb Salad
        Special Drink: Chai Tea
        """
@flock_tool
def get_price(item: str):
  """Provides the price of the requested menu item.
  
  Args:
    item: The name of the menu item.
  """
  # random price between 5 and 15
  return f"${random.randint(5, 15)}"

#################################


# create a flock
flock = Flock(name="Own Tools Demo",enable_logging=True)

# create an agent
agent = FlockFactory.create_default_agent(
  name="Menu Assistant",
  description="You are a helpful assistant",
  input="query",
  output="answer",
  tools=[get_specials, get_price],
)

# add the agent to the flock
flock.add_agent(agent)

# run the agent
flock.run(agent, input={"query": "What is the price of the soup special?"})

# save the flock to a file
flock.to_yaml_file(".flock/own_tools.flock.yaml", path_type="relative")








