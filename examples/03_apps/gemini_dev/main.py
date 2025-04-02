from typing import Optional
from pydantic import BaseModel, Field
from flock.core import FlockFactory, Flock
from flock.routers.default.default_router import DefaultRouter, DefaultRouterConfig



MODEL = "gemini/gemini-2.5-pro-exp-03-25" #"groq/qwen-qwq-32b"    #"openai/gpt-4o" # 
flock = Flock(model=MODEL)

# read .project/code.txt
with open(".project/code.txt", "r", encoding="utf-8") as f:
    code = f.read()

# read .project/llms-ctx.txt
with open(".project/llms-ctx.txt", "r", encoding="utf-8") as f:
    llms_ctx = f.read()
    
inputs = {
    "Code for the my project, the agent framework flock": code,
    "FastHTML Documentation": llms_ctx
}

prompt = """
I'm getting these errors:
INFO:     127.0.0.1:63465 - "GET /agents HTTP/1.1" 200 OK
INFO:     127.0.0.1:63463 - "GET /ui/ HTTP/1.1" 200 OK
INFO:     127.0.0.1:63464 - "GET /ui/get-agent-details-for-run?agent_name_selector=story_agent HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:63464 - "GET /ui/agent-details-content HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:63464 - "GET /ui/run-agent-content HTTP/1.1" 404 Not Found
INFO:     127.0.0.1:63464 - "GET /ui/get-agent-details-for-run?agent_name_selector=comic_book_issue_agent HTTP/1.1" 404 Not Found

Also you can't see anything in the UI because everything is just white
"""

dev_agent = FlockFactory.create_default_agent(name="dev_agent",
                                              description="An agent that is a master developer",
                                              input="inputs: dict[str, str], prompt: str",
                                              output="output_files: dict[str, str] | key is the filepath and value is the content of the file",
                                              max_tokens=60000,
                                              write_to_file=True)


flock.add_agent(dev_agent)
flock.run(start_agent="dev_agent", input={"inputs": inputs, "prompt": prompt})

