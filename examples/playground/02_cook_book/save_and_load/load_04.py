

from flock.core.flock import Flock


flock = Flock.load_from_file("flock.json")
agent = flock.agents

flock.run(start_agent=agent["bloggy"], input={"blog_idea": "A blog about cats"})