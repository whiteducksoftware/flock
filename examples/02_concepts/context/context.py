
from flock.core import Flock, FlockFactory
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.routers.default.default_router import DefaultRouter, DefaultRouterConfig

class ContextModule(FlockModule):
    def terminate(self, agent, inputs, result, context=None):
        context.set_variable("flock_agent1.a_random_name", "John Doe")
     

flock = Flock()



# Flock has an advanced context system that allows you to store and retrieve data
# across agents. The context is a dictionary that can be accessed and modified by 
# all agents in the flock via modules
# Agents will write their inputs and outputs to the context prefixed with "agentname."



flock_agent_1 = FlockFactory.create_default_agent(
    name="flock_agent1",
    input="",
    output="a_random_name: str",
)


flock_agent_2 = FlockFactory.create_default_agent(
    name="flock_agent2",
    input="a_random_name",
    output="name_in_caps: str",
)
flock_agent_2.add_module(ContextModule(name="context_module", config= FlockModuleConfig()))

# Agent3 will reverse John Doe to eoD nhoJ
flock_agent_3 = FlockFactory.create_default_agent(
    name="flock_agent3",
    input="flock_agent1.a_random_name",
    output="name_reversed: str",
    wait_for_input=True,
    print_context=True,
)


flock_agent_1.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=flock_agent_2.name))
flock_agent_2.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=flock_agent_3.name))
flock_agent_3.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=flock_agent_1.name))
flock.add_agent(flock_agent_1)
flock.add_agent(flock_agent_2)
flock.add_agent(flock_agent_3)

flock.run(
    input={},
    start_agent=flock_agent_1,
    agents=[flock_agent_1, flock_agent_2, flock_agent_3]
)