from typing import Optional
from pydantic import BaseModel, Field
from flock.core import FlockFactory, Flock

class Scene(BaseModel):
    title: str
    setting: str = Field(..., description="Setting of the scene")
    goal: str = Field(..., description="Goal of the scene")
    conflict: str = Field(..., description="Conflict of the scene")
    outcome: str = Field(..., description="Outcome of the scene")
    characters_involved: list[str] = Field(..., description="Name of characters/entities involved in the scene")
    story_beats: list[str] = Field(..., description="Story beats of the scene")


class Character(BaseModel):
    name: str = Field(..., description="Name of the character")
    role: str = Field(..., description="Role of the character")
    age: str = Field(..., description="Age of the character")
    appearance: str = Field(..., description="Appearance of the character")
    image_prompt: str = Field(..., description="Very detailed image prompt for image generation to represent the character")
    personality_traits: list[str] = Field(..., description="Personality traits of the character")
    backstory: str = Field(..., description="Backstory of the character")
    motivations: str = Field(..., description="Motivations of the character")
    weaknesses: str = Field(..., description="Weaknesses of the character")
    character_arc: str = Field(..., description="How the character evolves throughout the story")
    
class Chapter(BaseModel):
    title: str = Field(..., description="Title of the chapter")
    chapter_number: int = Field(..., description="Chapter number of the chapter")
    purpose: str = Field(..., description="Purpose of the chapter")
    summary: str = Field(..., description="Key events or chapter summary")
    scenes: list[Scene] = Field(..., description="Scenes of the chapter")
    

class Story(BaseModel):
    title: str
    status: str = Field(default="Idea", description="Idea, Drafting, Revising, Completed")
    genre: list[str] = Field(..., description="Genre(s) of the story")
    tone: str = Field(..., description="Tone of the story") 
    themes: list[str] = Field(..., description="Themes of the story")
    central_conflict: str = Field(..., description="Central conflict of the story")
    brief_summary: str = Field(..., description="Brief summary of the story")
    long_summary: str = Field(..., description="Long-form summary of the story.")
    characters: list[Character] = Field(..., description="Important characters and/or entities of the story")
    chapters: list[Chapter] = Field(..., description="All chapters of the story. At least one chapter per act.")
    
    
class StoryBible(BaseModel):
    timeline: dict[str, str]  = Field(..., description="Timeline of the story")
    worldbuilding_notes: dict[str, str]  = Field(..., description="Worldbuilding notes of the story")
    consistency_rules: list[str]  = Field(..., description="Consistency rules of the story")
    writing_reference: Optional[str] = Field(default=None, description="Writing reference and/or style guidelines")
    
class ComicBook(BaseModel):
    title: str = Field(..., description="Title of the comic book")
    issue_title: str = Field(..., description="Title of the issue")
    issue_number: int = Field(..., description="Issue number of the comic book")
    number_of_issues: int = Field(..., description="Number of issues needed to complete the story")
    issue_description: str = Field(..., description="Description of the issue")
    issue_start_scene: Scene = Field(..., description="Start scene of the issue")
    issue_end_scene: Scene = Field(..., description="End scene of the issue")
    issue_cover_image_prompt: str = Field(..., description="Cover image prompt for the issue")
    issue_pages: list[str] = Field(..., description="Description of the pages of the issue")

MODEL = "gemini/gemini-2.5-pro-exp-03-25" #"groq/qwen-qwq-32b"    #"openai/gpt-4o" # 
flock = Flock(model=MODEL)

story_agent = FlockFactory.create_default_agent(name="story_agent",
                                              description="An agent that is a master storyteller",
                                              input="story_idea: str",
                                              output="story: Story, story_bible: StoryBible",
                                              max_tokens=60000,
                                              write_to_file=True)

flock.add_agent(story_agent)

result = flock.run(start_agent=story_agent, input={'story_idea': 'A story about a young woman who discovers she has the ability to time travel.'}) 
story_overview = result.story
story_bible = result.story_bible

comic_book_agent = FlockFactory.create_default_agent(name="comic_book_agent",
                                              description="An agent that is a master comic book writer." 
                                              "Generates the next issue of the comic book based on the story and the past issues."
                                              "If no past issues are provided, it will generate the first issue.",
                                              input="story: Story, story_bible: StoryBible, past_issues: list[ComicBook]",
                                              output="comic_book: ComicBook",
                                              max_tokens=60000,
                                              write_to_file=True)

flock.add_agent(comic_book_agent)
result = flock.run(start_agent=comic_book_agent, input={'story': story_overview, 'story_bible': story_bible, 'past_issues': []}) 
comic_book = result.comic_book
