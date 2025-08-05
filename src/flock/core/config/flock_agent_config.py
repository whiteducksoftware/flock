"""Configuration settings for FlockAgent."""

from typing import Literal

from pydantic import BaseModel, Field


class FlockAgentConfig(BaseModel):
    """FlockAgentConfig is a class that holds the configuration for a Flock agent.
    
    It is used to store various settings and parameters that can be accessed throughout the agent's lifecycle.
    """

    write_to_file: bool = Field(
        default=False,
        description="Write the agent's output to a file.",
    )
    wait_for_input: bool = Field(
        default=False,
        description="Wait for user input after the agent's output is displayed.",
    )

    handoff_strategy: Literal["append", "override", "static", "map"] = Field(
        default="static",
        description="""Strategy for passing data to the next agent.
        
        example:
        ReviewAgent.next_agent = SummaryAgent
        ReviewAgent(output = "text:str, keywords:list[str], rating:int")
        SummaryAgent(input = "text:str, title:str")

        'append' means the difference in signature is appended to the next agent's input signature.
        SummaryAgent(input = "text:str, title:str, keywords:list[str], rating:int")

        'override' means the target agent's signature is getting overriden.
        SummaryAgent(input = "text:str, keywords:list[str], rating:int")

        'static' means the the target agent's signature is not changed at all.
        If source agent has no output fields that match the target agent's input,
        there will be no data passed to the next agent.
        SummaryAgent(input = "text:str, title:str")
        
        'map' means the source agent's output is mapped to the target agent's input
        based on 'handoff_map' configuration.

        """,
    )

    handoff_map: dict[str, str] | None = Field(
        default=None,
        description="""Mapping of source agent output fields to target agent input fields.
        
        Used with 'handoff_strategy' = 'map'.
        Example: {"text": "text", "keywords": "title"}
        
        If a field is not mapped, it will not be passed to the next agent.
        """,
    )
