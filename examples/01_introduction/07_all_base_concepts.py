import os
from flock.core import Flock, FlockFactory
from flock.core.flock_registry import flock_type 
from pydantic import BaseModel, Field
from typing import Optional, Literal

class Scene(BaseModel):
    title: str
    setting: str
    goal: str
    conflict: str
    outcome: str
    characters_involved: list[str]
    story_beats: list[str]


class Character(BaseModel):
    name: str
    role: str
    age: str
    appearance: str
    image_prompt: str
    personality_traits: list[str]
    backstory: str
    motivations: str
    weaknesses: str
    character_arc: str
    
class Chapter(BaseModel):
    title: str
    chapter_number: int
    purpose: str
    summary: str
    scenes: list[Scene]


@flock_type 
class Story(BaseModel):
    title: str
    status: Literal["Idea", "Drafting", "Revising", "Completed"]
    genre: list[str]
    tone: str
    themes: list[str]
    central_conflict: str
    brief_summary: str
    long_summary: str
    characters: list[Character]
    chapters: list[Chapter]
    
@flock_type 
class StoryBible(BaseModel):
    timeline: dict[str, str] 
    worldbuilding_notes: dict[str, str] 
    consistency_rules: list[str] 
    style_guide: str


MODEL = "gemini/gemini-2.5-pro-exp-03-25" 
flock = Flock(model=MODEL)


story_agent = FlockFactory.create_default_agent(
    name="story_agent",
    input="story_idea",
    output="story: Story, story_bible: StoryBible",
    max_tokens=60000,
)
flock.add_agent(story_agent)


flock.start_api(server_name="Example #07", create_ui=True)
flock.run(
    start_agent=story_agent, 
    input={"story_idea": "A story about a young woman who discovers she has the ability to time travel."}
)

