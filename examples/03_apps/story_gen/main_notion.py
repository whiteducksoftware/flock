import logging
import os
import sys
import time
from pprint import pprint
from typing import Optional, List, Dict, Any, Callable
from pydantic import BaseModel, Field
from flock.core import FlockFactory, Flock
from notion_client import Client, APIResponseError


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
    issue_cover_image_prompt: str = Field(..., description="Cover image prompt for the issue")
    issue_pages: list[str] = Field(..., description="Description of the pages of the issue")


# Define Notion Database IDs
NOTION_DB_IDS = {
    "characters": "1c2128b063d1807f8e69dd5715eea0aa",  # Keep the existing ID
    "story": "1c2128b063d18020850ceb65b652e93b",  # Add your Story database ID here
    "chapters": "1c2128b063d180728ac4fcf196e451d5",  # Add your Chapters database ID here
    "scenes": "1c2128b063d180d68e7ef1b97e2c418f",  # Add your Scenes database ID here
    "story_bible": "1c2128b063d1805ca471edee877708fb"  # Add your Story Bible database ID here
}

# Define a helper function to handle text limits for Notion
def create_rich_text(content: str, max_length: int = 2000) -> List[Dict[str, Any]]:
    """
    Create rich text objects for Notion API, handling text length limits.
    Notion has a 2000 character limit per rich_text object.
    
    Args:
        content: The text content to convert
        max_length: Maximum length per chunk (default 2000)
        
    Returns:
        List of rich_text objects for Notion API
    """
    if not content:
        return []
    
    # If content is shorter than max_length, return a single rich_text object
    if len(content) <= max_length:
        return [{"text": {"content": content}}]
    
    # Split content into chunks of max_length
    chunks = []
    for i in range(0, len(content), max_length):
        chunk = content[i:i + max_length]
        chunks.append({"text": {"content": chunk}})
    
    return chunks

def convert_dict_to_rich_text(data: dict) -> Dict[str, Any]:
    """Convert a dictionary to Notion rich text blocks for key-value pairs"""
    content = "\n".join([f"{key}: {value}" for key, value in data.items()])
    return create_rich_text(content)

def clear_database(notion_client: Client, database_id: str) -> None:
    """
    Clear all rows from a Notion database
    
    Args:
        notion_client: The Notion client instance
        database_id: The ID of the database to clear
    """
    if not database_id:
        print(f"Skipping database clear: No database ID provided")
        return
        
    try:
        # Query all pages in the database
        response = notion_client.databases.query(database_id=database_id)
        
        # Delete each page
        for page in response["results"]:
            try:
                notion_client.pages.update(
                    page_id=page["id"],
                    archived=True  # Archive the page (Notion's way of deleting)
                )
                print(f"Archived page {page['id']}")
            except Exception as e:
                print(f"Error archiving page {page['id']}: {e}")
                
        print(f"Cleared database {database_id}")
    except Exception as e:
        print(f"Error clearing database {database_id}: {e}")

def retry_api_call(api_function: Callable, *args, **kwargs) -> Any:
    """
    Retry an API call with exponential backoff
    
    Args:
        api_function: The API function to call
        *args, **kwargs: Arguments to pass to the API function
        
    Returns:
        The result of the API call
    """
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            return api_function(*args, **kwargs)
        except Exception as e:
            print(f"API error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"Failed after {max_retries} attempts")
                raise

def update_database_schema(notion_client: Client, database_id: str, properties: Dict[str, Any]) -> None:
    """
    Update a Notion database schema
    
    Args:
        notion_client: The Notion client instance
        database_id: The ID of the database to update
        properties: The properties to set
    """
    if not database_id:
        print(f"Skipping database schema update: No database ID provided")
        return
        
    try:
        retry_api_call(
            notion_client.databases.update,
            database_id=database_id,
            properties=properties
        )
        print(f"Updated database schema for {database_id}")
    except Exception as e:
        print(f"Error updating database schema for {database_id}: {e}")

def add_character_to_notion(notion_client: Client, character: Character) -> str:
    """
    Add a character to the Notion database
    
    Args:
        notion_client: The Notion client instance
        character: The character to add
        
    Returns:
        The ID of the created page
    """
    if not NOTION_DB_IDS["characters"]:
        print("Skipping character addition: No database ID provided")
        return ""
        
    # Filter out None values from personality_traits
    valid_traits = [trait for trait in character.personality_traits if trait is not None]
    
    # Prepare the character properties
    character_properties = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": character.name
                    }
                }
            ]
        },
        "Role": {
            "rich_text": create_rich_text(character.role)
        },
        "Age": {
            "rich_text": create_rich_text(character.age)
        },
        "Appearance": {
            "rich_text": create_rich_text(character.appearance)
        },
        "Image Prompt": {
            "rich_text": create_rich_text(character.image_prompt)
        },
        "Personality Traits": {
            "multi_select": [{"name": trait} for trait in valid_traits[:10]]  # Notion limits multi-select to 100 options
        },
        "Backstory": {
            "rich_text": create_rich_text(character.backstory)
        },
        "Motivations": {
            "rich_text": create_rich_text(character.motivations)
        },
        "Weaknesses": {
            "rich_text": create_rich_text(character.weaknesses)
        },
        "Character Arc": {
            "rich_text": create_rich_text(character.character_arc)
        }
    }
    
    try:
        response = retry_api_call(
            notion_client.pages.create,
            parent={"database_id": NOTION_DB_IDS["characters"]},
            properties=character_properties
        )
        print(f"Added character '{character.name}' with ID: {response['id']}")
        return response["id"]
    except Exception as e:
        print(f"Failed to add character '{character.name}': {e}")
        return ""

def add_scene_to_notion(notion_client: Client, scene: Scene, chapter_id: str = None) -> str:
    """
    Add a scene to the Notion database
    
    Args:
        notion_client: The Notion client instance
        scene: The scene to add
        chapter_id: Optional ID of the parent chapter page
        
    Returns:
        The ID of the created page
    """
    if not NOTION_DB_IDS["scenes"]:
        print("Skipping scene addition: No database ID provided")
        return ""
        
    # Prepare the scene properties
    scene_properties = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": scene.title
                    }
                }
            ]
        },
        "Setting": {
            "rich_text": create_rich_text(scene.setting)
        },
        "Goal": {
            "rich_text": create_rich_text(scene.goal)
        },
        "Conflict": {
            "rich_text": create_rich_text(scene.conflict)
        },
        "Outcome": {
            "rich_text": create_rich_text(scene.outcome)
        },
        "Characters Involved": {
            "multi_select": [{"name": character} for character in scene.characters_involved if character]
        },
        "Story Beats": {
            "rich_text": create_rich_text("\n• " + "\n• ".join(scene.story_beats))
        }
    }
    
    # Add relation to chapter if provided
    if chapter_id and chapter_id != "":
        scene_properties["Chapter"] = {
            "relation": [
                {
                    "id": chapter_id
                }
            ]
        }
    
    try:
        response = retry_api_call(
            notion_client.pages.create,
            parent={"database_id": NOTION_DB_IDS["scenes"]},
            properties=scene_properties
        )
        print(f"Added scene '{scene.title}' with ID: {response['id']}")
        return response["id"]
    except Exception as e:
        print(f"Failed to add scene '{scene.title}': {e}")
        return ""

def add_chapter_to_notion(notion_client: Client, chapter: Chapter, story_id: str = None) -> str:
    """
    Add a chapter to the Notion database
    
    Args:
        notion_client: The Notion client instance
        chapter: The chapter to add
        story_id: Optional ID of the parent story page
        
    Returns:
        The ID of the created page and a list of scene IDs
    """
    if not NOTION_DB_IDS["chapters"]:
        print("Skipping chapter addition: No database ID provided")
        return ""
        
    # Prepare the chapter properties
    chapter_properties = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": chapter.title
                    }
                }
            ]
        },
        "Chapter Number": {
            "number": chapter.chapter_number
        },
        "Purpose": {
            "rich_text": create_rich_text(chapter.purpose)
        },
        "Summary": {
            "rich_text": create_rich_text(chapter.summary)
        }
    }
    
    # Add relation to story if provided
    if story_id and story_id != "":
        chapter_properties["Story"] = {
            "relation": [
                {
                    "id": story_id
                }
            ]
        }
    
    try:
        response = retry_api_call(
            notion_client.pages.create,
            parent={"database_id": NOTION_DB_IDS["chapters"]},
            properties=chapter_properties
        )
        chapter_id = response["id"]
        print(f"Added chapter '{chapter.title}' with ID: {chapter_id}")
        
        # Add all scenes for this chapter
        scene_ids = []
        for scene in chapter.scenes:
            scene_id = add_scene_to_notion(notion_client, scene, chapter_id)
            if scene_id:
                scene_ids.append(scene_id)
        
        return chapter_id
    except Exception as e:
        print(f"Failed to add chapter '{chapter.title}': {e}")
        return ""

def add_story_to_notion(notion_client: Client, story: Story) -> str:
    """
    Add a story to the Notion database
    
    Args:
        notion_client: The Notion client instance
        story: The story to add
        
    Returns:
        The ID of the created page
    """
    if not NOTION_DB_IDS["story"]:
        print("Skipping story addition: No database ID provided")
        return ""
        
    # Filter out None values from themes
    valid_themes = [theme for theme in story.themes if theme is not None]
    valid_genres = [genre for genre in story.genre if genre is not None]
    
    # Prepare the story properties
    story_properties = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": story.title
                    }
                }
            ]
        },
        "Status": {
            "select": {
                "name": story.status
            }
        },
        "Genre": {
            "multi_select": [{"name": genre} for genre in valid_genres[:10]]  # Notion limits
        },
        "Tone": {
            "rich_text": create_rich_text(story.tone)
        },
        "Themes": {
            "multi_select": [{"name": theme} for theme in valid_themes[:10]]  # Notion limits
        },
        "Central Conflict": {
            "rich_text": create_rich_text(story.central_conflict)
        },
        "Brief Summary": {
            "rich_text": create_rich_text(story.brief_summary)
        },
        "Long Summary": {
            "rich_text": create_rich_text(story.long_summary)
        }
    }
    
    try:
        response = retry_api_call(
            notion_client.pages.create,
            parent={"database_id": NOTION_DB_IDS["story"]},
            properties=story_properties
        )
        story_id = response["id"]
        print(f"Added story '{story.title}' with ID: {story_id}")
        return story_id
    except Exception as e:
        print(f"Failed to add story '{story.title}': {e}")
        return ""

def add_story_bible_to_notion(notion_client: Client, story_bible: StoryBible, story_id: str = None) -> str:
    """
    Add a story bible to the Notion database
    
    Args:
        notion_client: The Notion client instance
        story_bible: The story bible to add
        story_id: Optional ID of the related story page
        
    Returns:
        The ID of the created page
    """
    if not NOTION_DB_IDS["story_bible"]:
        print("Skipping story bible addition: No database ID provided")
        return ""
        
    # Prepare the story bible properties
    story_bible_properties = {
        "Timeline": {
            "rich_text": convert_dict_to_rich_text(story_bible.timeline)
        },
        "Worldbuilding Notes": {
            "rich_text": convert_dict_to_rich_text(story_bible.worldbuilding_notes)
        },
        "Consistency Rules": {
            "rich_text": create_rich_text("\n• " + "\n• ".join(story_bible.consistency_rules))
        }
    }
    
    if story_bible.writing_reference:
        story_bible_properties["Writing Reference"] = {
            "rich_text": create_rich_text(story_bible.writing_reference)
        }
    
    # Add relation to story if provided
    if story_id and story_id != "":
        story_bible_properties["Story"] = {
            "relation": [
                {
                    "id": story_id
                }
            ]
        }
    
    try:
        response = retry_api_call(
            notion_client.pages.create,
            parent={"database_id": NOTION_DB_IDS["story_bible"]},
            properties=story_bible_properties
        )
        print(f"Added story bible with ID: {response['id']}")
        return response["id"]
    except Exception as e:
        print(f"Failed to add story bible: {e}")
        return ""

def setup_notion_databases(notion_client: Client) -> None:
    """
    Set up or update all Notion database schemas
    
    Args:
        notion_client: The Notion client instance
    """
    # Define database schemas
    database_schemas = {
        "characters": {
            "Name": {"title": {}},
            "Role": {"rich_text": {}},
            "Age": {"rich_text": {}},
            "Appearance": {"rich_text": {}},
            "Image Prompt": {"rich_text": {}},
            "Personality Traits": {"multi_select": {"options": []}},
            "Backstory": {"rich_text": {}},
            "Motivations": {"rich_text": {}},
            "Weaknesses": {"rich_text": {}},
            "Character Arc": {"rich_text": {}}
        },
        "scenes": {
            "Name": {"title": {}},
            "Setting": {"rich_text": {}},
            "Goal": {"rich_text": {}},
            "Conflict": {"rich_text": {}},
            "Outcome": {"rich_text": {}},
            "Characters Involved": {"multi_select": {"options": []}},
            "Story Beats": {"rich_text": {}},
            "Chapter": {"relation": {"database_id": NOTION_DB_IDS["chapters"], "single_property": True}}
        },
        "chapters": {
            "Name": {"title": {}},
            "Chapter Number": {"number": {}},
            "Purpose": {"rich_text": {}},
            "Summary": {"rich_text": {}},
            "Story": {"relation": {"database_id": NOTION_DB_IDS["story"], "single_property": True}},
            "Scenes": {"relation": {"database_id": NOTION_DB_IDS["scenes"], "single_property": False}}
        },
        "story": {
            "Name": {"title": {}},
            "Status": {"select": {"options": [
                {"name": "Idea", "color": "gray"},
                {"name": "Drafting", "color": "blue"},
                {"name": "Revising", "color": "yellow"},
                {"name": "Completed", "color": "green"}
            ]}},
            "Genre": {"multi_select": {"options": []}},
            "Tone": {"rich_text": {}},
            "Themes": {"multi_select": {"options": []}},
            "Central Conflict": {"rich_text": {}},
            "Brief Summary": {"rich_text": {}},
            "Long Summary": {"rich_text": {}}
        },
        "story_bible": {
            "Story": {"title": {}},
            "Timeline": {"rich_text": {}},
            "Worldbuilding Notes": {"rich_text": {}},
            "Consistency Rules": {"rich_text": {}},
            "Writing Reference": {"rich_text": {}},
            "Story": {"relation": {"database_id": NOTION_DB_IDS["story"], "single_property": True}}
        }
    }
    
    # Update each database schema if ID is provided
    for db_name, properties in database_schemas.items():
        if NOTION_DB_IDS[db_name]:
            # Skip relation properties if the related database ID is not set
            filtered_properties = {}
            for prop_name, prop_value in properties.items():
                if prop_value.get("relation") and not NOTION_DB_IDS.get(prop_value["relation"].get("database_id")):
                    continue
                filtered_properties[prop_name] = prop_value
            
            update_database_schema(notion_client, NOTION_DB_IDS[db_name], filtered_properties)

def push_story_to_notion(notion_client: Client, story: Story, story_bible: StoryBible) -> None:
    """
    Push the entire story and story bible to Notion
    
    Args:
        notion_client: The Notion client instance
        story: The story to push
        story_bible: The story bible to push
    """
    # Clear all databases first
    for db_name, db_id in NOTION_DB_IDS.items():
        if db_id:
            clear_database(notion_client, db_id)
    
    # Add the story
    story_id = add_story_to_notion(notion_client, story)
    
    # Add the story bible
    if story_id:
        add_story_bible_to_notion(notion_client, story_bible, story_id)
    
    # Add all characters
    for character in story.characters:
        add_character_to_notion(notion_client, character)
    
    # Add all chapters and scenes
    for chapter in story.chapters:
        add_chapter_to_notion(notion_client, chapter, story_id)
    
    print("Story successfully pushed to Notion")

# Main execution
MODEL = "gemini/gemini-2.5-pro-exp-03-25" #"groq/qwen-qwq-32b"    #"openai/gpt-4o" # 
flock = Flock(model=MODEL)
story_agent = FlockFactory.create_default_agent(name="story_agent",
                                              description="An agent that is a master storyteller",
                                              input="story_idea: str",
                                              output="story: Story, story_bible: StoryBible",
                                              max_tokens=60000)

flock.add_agent(story_agent)

result = flock.run(start_agent=story_agent, input={'story_idea': 'A story about a young woman who discovers she has the ability to time travel.'}) 

# Check for Notion API token
notion_token = os.getenv("NOTION_TOKEN_V2")
if not notion_token:
    print("Error: NOTION_TOKEN_V2 environment variable is not set. Please set it to your Notion integration token.")
    sys.exit(1)

# Initialize Notion client
try:
    notion = Client(auth=notion_token, log_level=logging.INFO)
    list_users_response = notion.users.list()
    print(f"Connected to Notion as {list_users_response['results'][0]['name']}")
except Exception as e:
    print(f"Error connecting to Notion API: {e}")
    sys.exit(1)

# Set up the database schemas
setup_notion_databases(notion)

# Push the entire story to Notion
push_story_to_notion(notion, result.story, result.story_bible)

