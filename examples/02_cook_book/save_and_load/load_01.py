

from flock.core import FlockAgent
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter


loaded_bloggy = FlockAgent.load_from_file("examples/data/bloggy.json")

result = loaded_bloggy.run(inputs={"blog_idea": "Idea for a blog post."})
PrettyPrintFormatter().display_data(result)




