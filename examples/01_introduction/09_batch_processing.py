import os
from flock.core import Flock, FlockFactory 


# Let's revisit the presentation agent but this time with batch processing!
MODEL = "openai/gpt-4o"


flock = Flock(name="example_09", description="This is a batch processing example", model=MODEL)


presentation_agent = FlockFactory.create_default_agent(
    name="my_presentation_agent",
    input="topic, audience, number_of_slides",
    output="fun_title, fun_slide_headers, fun_slide_summaries"
)
flock.add_agent(presentation_agent)

batch_data = [
    {"topic": "Robot Kittens", "audience": "Tech Enthusiasts"},
    {"topic": "AI in Gardening", "audience": "Homeowners"},
    {"topic": "The Future of Coffee", "audience": "Foodies"},
    {"topic": "Quantum Physics for Pets", "audience": "Animal Lovers"},
    {"topic": "Underwater Basket Weaving", "audience": "Extreme Sports Enthusiasts"},
    {"topic": "Space Tourism on a Budget", "audience": "Adventurous Retirees"},
    {"topic": "Blockchain Baking", "audience": "Culinary Students"},
    {"topic": "Time Travel Tourism", "audience": "History Buffs"},
    {"topic": "Telepathic Interior Design", "audience": "Minimalists"},
    {"topic": "Dancing with Dinosaurs", "audience": "Children's Entertainment Professionals"},
    {"topic": "Martian Fashion Trends", "audience": "Fashion Designers"},
    {"topic": "Edible Architecture", "audience": "Urban Planners"},
    {"topic": "Antigravity Yoga", "audience": "Fitness Instructors"},
    {"topic": "Digital Smell Technology", "audience": "Perfume Connoisseurs"},
    {"topic": "Musical Vegetables", "audience": "Orchestra Conductors"}
]

static_data = {"number_of_slides": 6}

silent_results = flock.run_batch( 
    start_agent=presentation_agent,
    batch_inputs=batch_data,
    static_inputs=static_data,
    parallel=True,
    max_workers=2,
    silent_mode=False,
    return_errors=True
)

print("\nBatch finished. Results (or errors):")
for res in silent_results:
    print(res)