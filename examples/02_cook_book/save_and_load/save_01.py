

from typing import Any, Dict, Type
from flock.core import FlockAgent
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter


# Save and load agents

bloggy = FlockAgent(name="bloggy", input="blog_idea", output="funny_blog_title, blog_headers") 
bloggy.save_to_file("examples/data/bloggy.json")


