from flock.core import Flock, FlockFactory
from flock.core.flock_api import FlockAPI


MODEL = "openai/gpt-4o"

flock = Flock(model=MODEL)

bloggy = FlockFactory.create_default_agent(
    name="bloggy",
    input="blog_idea",
    output="funny_blog_title, blog_headers",
)
flock.add_agent(bloggy)

# Swagger: http://127.0.0.1:8344/docs
# Redoc: http://127.0.0.1:8344/redoc
# POST: http://127.0.0.1:8344/run 
api = FlockAPI(flock)
api.start()