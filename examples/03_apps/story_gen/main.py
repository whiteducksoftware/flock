from typing import Optional
from pydantic import BaseModel, Field
from flock.core import FlockFactory, Flock, flock_registry
from flock.core.flock_registry import flock_type
from flock.routers.default.default_router import DefaultRouter, DefaultRouterConfig

FlockRegistry = flock_registry.get_registry()

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
    


########################################################

class Prompt(BaseModel):
    prompt: str = Field(..., description="Detailed Prompt for image generation")
    title: str = Field(..., description="Title of the prompt")
    
# Define the whole comic book series as a whole
    
class Issue(BaseModel):
    title: str = Field(..., description="Title of the issue")
    issue_number: int = Field(..., description="Issue number of the issue")
    issue_description: str = Field(..., description="Description/Summary of the issue")
    issue_scenes: dict[int,str] = Field(..., description="Scenes of the story the issue visualizes. Key is the page number and value is the scene title as defined in the story chapters.")
    issue_cover_image_prompt: str = Field(..., description="Cover image prompt for the issue")
    number_of_pages: int = Field(..., description="Number of pages in the issue")
    number_of_panels: int = Field(..., description="Number of panels in the issue")
    linked_concept_art_prompts: list[str] = Field(..., description="Concept art prompts that are linked to the issue. The prompts are linked to the issue by the title of the prompt.")
    
class ComicBookSeries(BaseModel):
    title: str = Field(..., description="Title of the comic book series")
    issues: list[Issue] = Field(..., description="Issues of the comic book series")
    concept_art_prompts: list[Prompt] = Field(..., description="Concept art prompts for the comic book series. Includes character concept art, setting concept art, etc. Everything that needs consistency across the series.")
    
    
########################################################
    
class PageLayout(BaseModel):
    issue_number: int = Field(..., description="Issue number of the page layout")
    page_number: int = Field(..., description="Page number of the page layout")
    amount_of_panels: int = Field(..., description="Amount of panels on the page")
    layout_description: str = Field(..., description="Description of the panel layout of the page")
    page_prompt: str = Field(..., description="Prompt for the page")
    story_scene_title: str = Field(..., description="Title of the story scene that is depicted in the page")
    
class IssueLayout(Issue):
    page_layouts: list[PageLayout] = Field(..., description="Page layouts for the issue")
    
    
@flock_type 
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
    
@flock_type 
class StoryBible(BaseModel):
    timeline: dict[str, str]  = Field(..., description="Timeline of the story")
    worldbuilding_notes: dict[str, str]  = Field(..., description="Worldbuilding notes of the story")
    consistency_rules: list[str]  = Field(..., description="Consistency rules of the story")
    writing_reference: Optional[str] = Field(default=None, description="Writing reference and/or style guidelines")

MODEL = "gemini/gemini-2.5-pro-exp-03-25" #"groq/qwen-qwq-32b"    #"openai/gpt-4o" # 
flock = Flock(model=MODEL)


story_agent = FlockFactory.create_default_agent(name="story_agent",
                                              description="An agent that is a master storyteller",
                                              input="story_idea: str",
                                              output="story: Story, story_bible: StoryBible",
                                              max_tokens=60000,
                                              write_to_file=True)


flock.add_agent(story_agent)
result = flock.run(start_agent=story_agent, 
                   input={'story_idea': 
                       'In a world right at the cusp between LLMs and AGI some guy is experiencing the most peculiar story.' 
                       'Absurdist Fiction, Satire, Technological Comedy. As much content as possible. At least 10.000 words'}) 



# story_agent = FlockFactory.create_default_agent(name="story_agent",
#                                               description="An agent that is a master storyteller",
#                                               input="story_idea: str",
#                                               output="story: Story, story_bible: StoryBible",
#                                               max_tokens=60000,
#                                               write_to_file=True)

# comic_book_series_agent = FlockFactory.create_default_agent(name="comic_book_series_agent",
#                                               description="An agent that is a master comic book writer." 
#                                               "Generates a comic book series based on a story and a story bible.",
#                                               input="story: Story, story_bible: StoryBible",
#                                               output="comic_book_series: ComicBookSeries",
#                                               max_tokens=60000,
#                                               write_to_file=True)

# comic_book_issue_agent = FlockFactory.create_default_agent(name="comic_book_issue_agent",
#                                               description="An agent that is a master comic book writer." 
#                                               "Generates details for each issue of the comic book series.",
#                                               input="comic_book_series: ComicBookSeries",
#                                               output="comic_book_pages: list[PageLayout]",
#                                               max_tokens=60000,
#                                               write_to_file=True)


# story_agent.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=comic_book_series_agent.name))
# comic_book_series_agent.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=comic_book_issue_agent.name))

# flock.add_agent(comic_book_series_agent)	
# flock.add_agent(comic_book_issue_agent)
# flock.start_api(server_name="Storyteller Agent", create_ui=True)

# result = flock.run(start_agent=story_agent, input={'story_idea': 'A story about a young woman who discovers she has the ability to time travel.'}) 
# story_overview = result.story
# story_bible = result.story_bible



# flock.add_agent(comic_book_series_agent)
# result = flock.run(start_agent=comic_book_series_agent, input={'story': story_overview, 'story_bible': story_bible}) 
# comic_book_series = result.comic_book_series
