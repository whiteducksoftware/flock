"""Example usage of the Hierarchical Memory Module for AI agents."""

import asyncio
from typing import Dict, Any

from flock.core import FlockFactory
from flock.core.logging.formatters.themes import OutputTheme
from flock.evaluators.memory.hierarchical_evaluator import HierarchicalMemoryEvaluator, HierarchicalMemoryEvaluatorConfig
from flock.modules.hierarchical.memory import ConceptRelationType, HierarchicalMemoryModuleConfig
from flock.modules.hierarchical.module import HierarchicalMemoryModule



async def main():
    """Demonstrate the hierarchical memory capabilities."""
    
    # Create an agent with hierarchical memory
    memory_config = HierarchicalMemoryEvaluatorConfig(
        folder_path="hierarchical_memory/",
        enable_hierarchical_concepts=True,
        upward_propagation_factor=0.8,
        downward_propagation_factor=0.6,
        similarity_threshold=0.5,
        splitting_mode="semantic",
        save_after_update=True,
    )
    memory_module_config = HierarchicalMemoryModuleConfig(
        folder_path="hierarchical_memory/",
        enable_hierarchical_concepts=True,
        upward_propagation_factor=0.8,
        downward_propagation_factor=0.6,
        similarity_threshold=0.5,
        splitting_mode="semantic"
    )
    # Create the memory module with the configuration
    memory_eval = HierarchicalMemoryEvaluator(name="hierarchical_memory", config=memory_config)
    memory_module = HierarchicalMemoryModule(name="hierarchical_memory", config=memory_module_config)
    
    # Create the agent with the memory module
    agent = FlockFactory.create_default_agent(
        model="openai/gpt-4o",
        name="hierarchical_memory_agent", 
        input="data", 
        output_theme=OutputTheme.aardvark_blue
    )
    
    # Replace the default evaluator with our hierarchical memory module
    agent.evaluator = memory_eval
    

    
    # Add some initial data with implicit hierarchies
    print("Adding initial information...")
    await agent.run_async(inputs={"data": "Andre is 38 years old and author of the agent framework 'flock'"})
    await agent.run_async(inputs={"data": "Andre works for White Duck"})
    await agent.run_async(inputs={"data": "Andre has two cats"})
    await agent.run_async(inputs={"data": "White Duck is a cloud consulting company"})
    await agent.run_async(inputs={"data": "Flock is an agent framework designed for scalable multi-agent systems"})
    
    # Add data about Andre's cats with names
    await agent.run_async(inputs={"data": "One of Andre's cats is named Luna"})
    await agent.run_async(inputs={"data": "The other cat is named Lucy"})
    
    # Add location information
    await agent.run_async(inputs={"data": "Andre lives in Germany"})
    await agent.run_async(inputs={"data": "Germany is in Europe"})
    
    # Add explicit hierarchical relationships
    print("\nAdding explicit hierarchical relationships...")
    
    
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="cat",
        parent_concept="pet",
        relation_type=ConceptRelationType.IS_A
    )
    
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="dog",
        parent_concept="pet",
        relation_type=ConceptRelationType.IS_A
    )
    
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="luna",
        parent_concept="cat",
        relation_type=ConceptRelationType.IS_A
    )
    
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="lucy",
        parent_concept="cat",
        relation_type=ConceptRelationType.IS_A
    )
    
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="flock",
        parent_concept="agent framework",
        relation_type=ConceptRelationType.IS_A
    )
    
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="agent framework",
        parent_concept="software",
        relation_type=ConceptRelationType.IS_A
    )
    
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="white duck",
        parent_concept="company",
        relation_type=ConceptRelationType.IS_A
    )
    
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="company",
        parent_concept="organization",
        relation_type=ConceptRelationType.IS_A
    )
    
    # Add compositional relationships
    await memory_module.add_hierarchical_relationship(
        agent=agent,
        child_concept="germany",
        parent_concept="europe",
        relation_type=ConceptRelationType.PART_OF
    )
    
    # Query the memory with hierarchical awareness
    print("\nQuerying memory with hierarchical awareness...")
    
    # This query should retrieve information about Luna and Lucy by
    # traversing up from the specific cat names to the "cat" concept
    query_result = await memory_module.search_memory(
        agent=agent, 
        query={"query": "What pets does Andre have?"}
    )
    
    print("\nQuery: What pets does Andre have?")
    if "memory_results" in query_result:
        print(f"Found {len(query_result['memory_results'])} results:")
        for i, result in enumerate(query_result["memory_results"]):
            print(f"  Result {i+1}: {result.content[:100]}..." if len(result.content) > 100 else result.content)
    else:
        print("No results found.")
    
    # This query tests the ability to retrieve information by traversing down from
    # Europe to Germany and finding relevant information
    query_result = await memory_module.search_memory(
        agent=agent, 
        query={"query": "Where in Europe does Andre live?"}
    )
    
    print("\nQuery: Where in Europe does Andre live?")
    if "memory_results" in query_result:
        print(f"Found {len(query_result['memory_results'])} results:")
        for i, result in enumerate(query_result["memory_results"]):
            print(f"  Result {i+1}: {result.content[:100]}..." if len(result.content) > 100 else result.content)
    else:
        print("No results found.")
    
    # Save the final memory and concept graph image
    memory_module.save_memory()
    print("\nMemory saved with hierarchical concept graph.")


if __name__ == "__main__":
    asyncio.run(main())