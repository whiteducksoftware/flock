from flock.core import Flock, FlockFactory



flock = Flock()

website_agent = FlockFactory.create_default_agent(name="Website Agent", 
                                                  description="A website creator that creates a website for rendering a given prompt",
                                                  input="fields_to_render: list[str], design_style: str",
                                                  output="jinja2_template: str | A template for presenting the fields in a website")

flock.add_agent(website_agent)
flock.start_api()

flock.run(start_agent=website_agent, input={"fields_to_render": ["project_title", "project_descriptions", "tasks: list[str]"], "design_style": "very sleek and modern"})
