import numpy as np
from flock.core import Flock, FlockAgent
from pydantic import BaseModel, Field
import matplotlib.pyplot as plt

from flock.core.flock_agent import FlockAgentConfig, FlockAgentOutputConfig

from dspy import Image

from flock.core.logging.formatters.themes import OutputTheme

# Class for parts of the final image
class ImagePart(BaseModel):
    image_part: str = Field(description="Part of the image to draw")
    list_of_coordinates: list[tuple[float,float]] = Field(default_factory=list, description="List of coordinates to connect to create a part of the image. X<10 - Y<10 - coordinates are floats - use this accuracy for better results")
    matplotlib_color: str = Field(default="b", description="Color of the line in the plot")

# global variables
MODEL = "openai/gpt-4"
image : Image = None
image_parts: list[ImagePart] = None
counter = 0

# draws the image by iterating over the list of image parts and connecting the coordinates
async def draw_image(agent,input,output):
    global image_parts
    global image
    global counter
    counter += 1

    image_parts = output["list_of_all_image_parts"]

    plt.figure(figsize=(10, 10))
    
    for image_part in image_parts:
        coordinates = np.array(image_part.list_of_coordinates)  # Convert list to numpy array
        if len(coordinates) > 1:
            plt.plot(coordinates[:, 0], coordinates[:, 1], marker='x', linestyle='-', markersize=5, color=image_part.matplotlib_color)
    
    plt.axis('equal')  # Keep aspect ratio
    plt.grid(True)
    
    save_path = f"plot_{counter}.png"
    plt.savefig(save_path, dpi=300)

    image = Image.from_file(save_path)
    
    plt.show()

# if there is a previous image, load it and give it to the agent
async def load_prev_image(agent: FlockAgent,inputs):
    global image
    global image_parts
    if image is not None:
        agent.description = "Draws an image by connecting the coordinates of the image parts. Improves the image by adding new parts to the previous image and/or changing them."
        agent.input = "subject_to_draw: str, prev_image: dspy.Image | result of rendered image parts, prev_image_parts: list[ImagePart] | previously generated image parts"
        inputs["prev_image"] = image
        inputs["prev_image_parts"] = image_parts



# Generate the plot

flock = Flock(local_debug=True)

config = FlockAgentConfig(agent_type_override="ChainOfThought")

agent = FlockAgent(name="the_painter", 
                    input="subject_to_draw: str", 
                    description="Draws an image by connecting the coordinates of the image parts. 0/0 is bottom left corner - 10/10 is top right corner",
                    output="list_of_all_image_parts: list[ImagePart] | list of all image parts to draw by connecting the coordinates",
                    config=config, 
                    terminate_callback=draw_image,
                    initialize_callback=load_prev_image,
                    output_config=FlockAgentOutputConfig(
                        render_table=True,
                        theme=OutputTheme.abernathy
                    ))

agent.hand_off = agent

result = flock.run(start_agent=agent, agents=[agent])




