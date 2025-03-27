from typing import Optional
from pydantic import BaseModel, Field
from flock.core import FlockFactory, Flock


class Story(BaseModel):
    title: str
    status: str = Field(default="Idea", description="Idea, Drafting, Revising, Completed")
    genre: str
    tone: str
    themes: list[str]
    central_conflict: str
    brief_summary: str
    characters: list["Character"] = []
    chapters: list["Chapter"] = []
    
    
class Character(BaseModel):
    name: str
    role: str  # Protagonist, Antagonist, Supporting
    age: int = Field(default=None, description="Age of the character")
    appearance: Optional[str] = None
    personality_traits: list[str] = []
    backstory: Optional[str] = None
    motivations: Optional[str] = None
    weaknesses: Optional[str] = None
    character_arc: Optional[str] = None
    
class Chapter(BaseModel):
    title: str
    chapter_number: int
    purpose: Optional[str] = None
    summary: Optional[str] = Field(default=None, description="Key events or chapter summary")
    scenes: list["Scene"] = []
    
    

class Scene(BaseModel):
    title: str
    setting: Optional[str] = None
    goal: Optional[str] = None
    conflict: Optional[str] = None
    outcome: Optional[str] = None
    characters_involved: list[Character] = []
    story_beats: list[str] = []
    
    
class StoryBible(BaseModel):
    timeline: dict[str, str]  # Date/Event mapping
    worldbuilding_notes: dict[str, str]  # Topic/Description
    consistency_rules: list[str]  # List of rules
    writing_reference: Optional[str] = None
    
MODEL = "groq/qwen-qwq-32b"    
flock = Flock(model=MODEL)
brainstorm_agent = FlockFactory.create_default_agent(name="brainstorm_agent",
                                              description="A flock of agents that brainstorms about the story",
                                              input="story_idea: str",
                                              output="story_outlines: list[Story] | Three differentstory outlines",
                                              max_tokens=4096*8)

flock.add_agent(brainstorm_agent)

flock.run(start_agent=brainstorm_agent) 

