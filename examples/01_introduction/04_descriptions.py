from flock.core import Flock, FlockFactory
 
flock = Flock()

# --------------------------------
# Add descriptions
# --------------------------------
# If you NEED your agent to handle edge cases, you can add descriptions to your agents
# The descriptions property on the FlockAgent class allows you to add a description to your agent,
# while with "|" you can specify descriptions of the input and output fields of the agent.

a_cat_naming_agent = FlockFactory.create_default_agent(
    name="cat_naming_agent",
    input="animal | the animal to create a cute name for",
    output="""
        cute_name: list[str] | a list of 5 cute names IN ALL CAPS, 
        error_message | an error message if the input is not a cat
    """,
)
flock.add_agent(a_cat_naming_agent)


flock.run(
    start_agent=a_cat_naming_agent, 
    input={"animal": "My new kitten"}
)


