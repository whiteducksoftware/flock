"""
Azure AI Search Tools Example with Flock Agent Framework

This example demonstrates how to use Azure AI Search tools within the Flock agent framework.
It creates agents that can:
1. Create a search index
2. Upload documents to the index
3. Query the index with both text and filter criteria
4. Process and summarize search results

Requirements:
- Set the following environment variables:
  - AZURE_SEARCH_ENDPOINT: Your Azure AI Search service endpoint URL
  - AZURE_SEARCH_API_KEY: Your Azure AI Search API key
"""

import os
import time
import uuid
import json
from dotenv import load_dotenv

from flock.core import Flock, FlockFactory
from flock.core.logging.formatters.themes import OutputTheme
from flock.core.tools.azure_tools import (
    azure_search_initialize_clients,
    azure_search_create_index,
    azure_search_upload_documents,
    azure_search_query,
    azure_search_get_document,
    azure_search_delete_documents,
    azure_search_list_indexes,
    azure_search_get_index_statistics
)
from flock.core.tools import basic_tools

# Load environment variables from .env file
load_dotenv()

# Make sure Azure Search credentials are set
if not os.environ.get("AZURE_SEARCH_ENDPOINT") or not os.environ.get("AZURE_SEARCH_API_KEY"):
    raise ValueError(
        "Please set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY environment variables"
    )

# Create a unique index name for this example
timestamp = int(time.time())
random_id = str(uuid.uuid4())[:8]
INDEX_NAME = f"flock-example-{timestamp}-{random_id}"
os.environ["AZURE_SEARCH_INDEX_NAME"] = INDEX_NAME

# --------------------------------
# Create the flock
# --------------------------------
flock = Flock()

# --------------------------------
# Define our agents
# --------------------------------

# 1. Index Creator Agent
# This agent creates a search index with appropriate schema
index_creator = FlockFactory.create_default_agent(
    name="index_creator",
    input="index_requirements",
    output="created_index_details",
    tools=[
        azure_search_create_index,
        basic_tools.code_eval,
        basic_tools.json_parse_safe
    ],
    enable_rich_tables=True,
    output_theme=OutputTheme.adventuretime,
)

# 2. Document Uploader Agent
# This agent uploads sample documents to the search index
document_uploader = FlockFactory.create_default_agent(
    name="document_uploader",
    input="created_index_details, documents_to_upload",
    output="upload_results",
    tools=[
        azure_search_upload_documents,
        basic_tools.code_eval,
        basic_tools.json_parse_safe
    ],
    enable_rich_tables=True,
    output_theme=OutputTheme.adventuretime,
)

# 3. Search Agent
# This agent searches the index and processes results
search_agent = FlockFactory.create_default_agent(
    name="search_agent",
    input="upload_results, search_query, filter_criteria",
    output="search_results: dict, relevant_documents: list, summary: str",
    tools=[
        azure_search_query,
        azure_search_get_document,
        basic_tools.code_eval,
        basic_tools.json_parse_safe
    ],
    enable_rich_tables=True,
    output_theme=OutputTheme.adventuretime,
)

# 4. Cleanup Agent (optional)
# This agent gets statistics and can delete documents if needed
cleanup_agent = FlockFactory.create_default_agent(
    name="cleanup_agent",
    input="search_results",
    output="index_statistics: dict, cleanup_recommendation: str",
    tools=[
        azure_search_get_index_statistics,
        azure_search_list_indexes,
        azure_search_delete_documents,
        basic_tools.code_eval
    ],
    enable_rich_tables=True,
    output_theme=OutputTheme.adventuretime,
)

# --------------------------------
# Configure agent flow
# --------------------------------
# Set up the agent sequence:
# index_creator -> document_uploader -> search_agent -> cleanup_agent
from flock.routers.default.default_router import DefaultRouter, DefaultRouterConfig

index_creator.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=document_uploader.name))
document_uploader.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=search_agent.name))
search_agent.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=cleanup_agent.name))

# Add all agents to the flock
flock.add_agent(index_creator)
flock.add_agent(document_uploader)
flock.add_agent(search_agent)
flock.add_agent(cleanup_agent)

# --------------------------------
# Define sample data
# --------------------------------
# Define our sample documents
sample_documents = [
    {
        "id": "doc1",
        "title": "Azure AI Search Overview",
        "content": "Azure AI Search is a cloud search service with built-in AI capabilities.",
        "category": "cloud",
        "rating": 5
    },
    {
        "id": "doc2",
        "title": "Python Development Best Practices",
        "content": "Write clean, maintainable Python code by following established best practices.",
        "category": "development",
        "rating": 4
    },
    {
        "id": "doc3",
        "title": "Azure and Python Integration",
        "content": "Learn how to use Azure services with Python applications effectively.",
        "category": "cloud",
        "rating": 5
    },
    {
        "id": "doc4",
        "title": "Search Engine Optimization",
        "content": "Improve your website's visibility in search engine results pages.",
        "category": "marketing",
        "rating": 3
    },
    {
        "id": "doc5",
        "title": "Machine Learning on Azure",
        "content": "Train and deploy machine learning models using Azure ML.",
        "category": "ai",
        "rating": 5
    }
]

# Define index requirements
index_requirements = """
Create a search index with the following fields:
- id: string, key field
- title: string, searchable, sortable
- content: string, searchable
- category: string, filterable
- rating: integer, filterable, sortable

The index name should be dynamically set from the AZURE_SEARCH_INDEX_NAME environment variable.
"""

# --------------------------------
# Run the flock
# --------------------------------
# Start the agent workflow
flock.run(
    start_agent=index_creator,
    input={
        "index_requirements": index_requirements,
        "documents_to_upload": json.dumps(sample_documents),
        "search_query": "Azure cloud capabilities",
        "filter_criteria": "rating eq 5"
    }
)

# --------------------------------
# Cleanup
# --------------------------------
# Delete the test index after running the example
print(f"\nCleaning up: Deleting index '{INDEX_NAME}'...")
try:
    clients = azure_search_initialize_clients()
    index_client = clients["index_client"]
    index_client.delete_index(INDEX_NAME)
    print(f"Index '{INDEX_NAME}' deleted successfully.")
except Exception as e:
    print(f"Warning: Failed to delete test index '{INDEX_NAME}': {e}")

print("\nExample completed!") 