import json
from typing import Optional
from pydantic import BaseModel, Field
from flock.core import FlockFactory, Flock


class DynamicHTMLApp(BaseModel):
    name: str = Field(..., description="Name of the app")
    requirements: list[str] = Field(..., description="User specified requirements for the app")
    description: str = Field(..., description="High level description of the data and functionality of the app, as well as design decisions")
    html_content: str = Field(..., description="HTML content of the app")
    css_content: str = Field(..., description="CSS content of the app")
    js_content: str = Field(..., description="JS content of the app")
    html_file: str = Field(..., description="HTML file name")
    css_file: str = Field(..., description="CSS file name")
    js_file: str = Field(..., description="JS file name")
    
MODEL = "gemini/gemini-2.5-pro-exp-03-25" #"groq/qwen-qwq-32b"    #"openai/gpt-4o" # 
flock = Flock(model=MODEL)

app_agent = FlockFactory.create_default_agent(name="app_agent",
                                              description="An agent that generates a static html app based on the requirements and the input_data. "
                                              "The input_data is the content of a json file that contains the data to be displayed in the app."
                                              "The final app should load the input_data from json files in a folder called 'data' in the same directory as the app."
                                              "The app should present the content of the input file as if designed by a professional UX designer and dedicated to the data in the input file."
                                              "For example, if the input data is a story, the app should present the story as if it is a dedicated story app."
                                              "If for example the input data is a list of products, the app should present the products as if it is a dedicated product app.",
                                              input="requirements: str, input_data: str",
                                              output="app: DynamicHTMLApp",
                                              max_tokens=60000)

flock.add_agent(app_agent)

requirements = "elegant, professional, color-coded, modern, dark mode"
input_file = "output/comic_book_series_agent_output_20250330_044131.json"
output_dir = "output/apps/"

# Load the input data as string 
with open(input_file, 'r') as f:
    input_data = f.read()

result = flock.run(start_agent=app_agent, input={'requirements': requirements, 'input_data': input_data}) 
app = result.app

#save html, css, js to files
with open(output_dir + app.html_file, 'w') as f:
    f.write(app.html_content)
with open(output_dir + app.css_file, 'w') as f:
    f.write(app.css_content)
with open(output_dir + app.js_file, 'w') as f:
    f.write(app.js_content)

print(f"App saved to {output_dir + app.html_file}")
