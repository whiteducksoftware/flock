

from flock.core import FlockAgent
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter

# chatty is a rather compley agent. no problem for Flock to load it.
loaded_bloggy = FlockAgent.load_from_file("examples/data/chatty.json")

result = loaded_bloggy.run(inputs={})
PrettyPrintFormatter().display_data(result)