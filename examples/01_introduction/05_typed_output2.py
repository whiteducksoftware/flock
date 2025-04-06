from dataclasses import dataclass
from pprint import pprint
from typing import Literal

from flock.core import Flock, FlockFactory
from flock.core.flock_registry import flock_type
from pydantic import BaseModel

# --------------------------------
# Define the data model for a random person
# --------------------------------
@flock_type
class RandomPerson(BaseModel):
    name: str
    age: int
    gender: Literal["female", "male"]
    job: str
    favorite_movie: str  
    short_bio: str


   
flock = Flock()

# --------------------------------
# Define the Random User List Agent
# --------------------------------
# This agent ("people_agent") is responsible for generating a list of random users.
# It requires the input "amount_of_people" and produces an output "random_user_list" 
# which is a RandomUserList object.
# Internally all dataclass, pydantic basemodels and alias are supported
people_agent = FlockFactory.create_default_agent(
    name="people_agent",
    input="amount_of_people",
    output="random_user_list: list[RandomPerson]",
)
flock.add_agent(people_agent)

# --------------------------------
# Run the agent to generate random users
# --------------------------------
# We execute the agent asynchronously, passing in the desired amount of people.
# The result is a namespace containing the generated random user list.
result =  flock.run(
    start_agent=people_agent,
    input={"amount_of_people": "10"},
)

# --------------------------------
# Process and display the result
# --------------------------------
# Here we print the number of users generated to verify our agent's output.
pprint(len(result.random_user_list))


