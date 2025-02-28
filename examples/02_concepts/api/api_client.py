import httpx

from flock.core.flock_api import FlockAPIRequest
from rich.console import Console
from rich.pretty import Pretty


console = Console()

payload = FlockAPIRequest(agent_name="bloggy", inputs={"blog_idea": "A blog about cats"})

response = httpx.post("http://127.0.0.1:8344/run/flock",content=payload.model_dump_json())
response.raise_for_status()

pretty = Pretty(response.json())
console.print(pretty)



