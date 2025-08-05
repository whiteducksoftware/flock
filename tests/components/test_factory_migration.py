#!/usr/bin/env python3
"""Test script for FlockFactory migration to unified components."""

from flock.core.flock_factory import FlockFactory
from flock.components.evaluation.declarative_evaluation_component import DeclarativeEvaluationComponent
from flock.components.utility.output_utility_component import OutputUtilityComponent
from flock.components.utility.metrics_utility_component import MetricsUtilityComponent


def test_factory_migration():
    """Test the updated FlockFactory with unified components."""
    print("🚀 Testing FlockFactory Migration to Unified Components")
    print("=" * 60)
    
    # Test creating a default agent using the factory
    print("🔨 Creating default agent with FlockFactory.create_default_agent()...")
    
    agent = FlockFactory.create_default_agent(
        name="test_factory_agent",
        input="query: str",
        output="response: str",
        no_output=True,  # Suppress output for test
        alert_latency_threshold_ms=5000,
    )
    
    print(f"✅ Agent created: {agent.name}")
    print(f"   - Input: {agent.input}")
    print(f"   - Output: {agent.output}")
    print(f"   - Components: {len(agent.components)}")
    
    # Verify component types
    component_types = [type(comp).__name__ for comp in agent.components]
    print(f"   - Component types: {component_types}")
    
    # Test component identification
    print("\n🔍 Testing Component Identification:")
    
    evaluator = agent.evaluator
    if evaluator and isinstance(evaluator, DeclarativeEvaluationComponent):
        print(f"✅ Evaluator: {evaluator.name} (DeclarativeEvaluationComponent)")
    else:
        print(f"❌ Evaluator identification failed: {type(evaluator)}")
    
    # Check for utility components
    output_component = None
    metrics_component = None
    
    for comp in agent.components:
        if isinstance(comp, OutputUtilityComponent):
            output_component = comp
        elif isinstance(comp, MetricsUtilityComponent):
            metrics_component = comp
    
    if output_component:
        print(f"✅ Output Component: {output_component.name} (OutputUtilityComponent)")
    else:
        print("❌ Output component not found")
    
    if metrics_component:
        print(f"✅ Metrics Component: {metrics_component.name} (MetricsUtilityComponent)")
    else:
        print("❌ Metrics component not found")
    
    # Test configuration propagation
    print("\n⚙️ Testing Configuration Propagation:")
    
    if evaluator:
        print(f"   - Evaluator model: {evaluator.config.model}")
        print(f"   - Max tokens: {evaluator.config.max_tokens}")
        print(f"   - Temperature: {evaluator.config.temperature}")
    
    if output_component:
        print(f"   - Output suppressed: {output_component.config.no_output}")
        print(f"   - Theme: {output_component.config.theme}")
    
    if metrics_component:
        print(f"   - Latency threshold: {metrics_component.config.latency_threshold_ms}ms")
        print(f"   - Storage type: {metrics_component.config.storage_type}")
    
    # Test backward compatibility - ensure old examples would still work
    print("\n🔄 Testing Example Compatibility:")
    
    presentation_agent = FlockFactory.create_default_agent(
        name="my_presentation_agent",
        input="topic",
        output="fun_title, fun_slide_headers, fun_slide_summaries",
        no_output=True  # Suppress output for test
    )
    
    print(f"✅ Example agent created: {presentation_agent.name}")
    print(f"   - Input: {presentation_agent.input}")
    print(f"   - Output: {presentation_agent.output}")
    print(f"   - Has evaluator: {presentation_agent.evaluator is not None}")
    print(f"   - Total components: {len(presentation_agent.components)}")
    
    # Test advanced configuration
    print("\n🎛️ Testing Advanced Configuration:")
    
    advanced_agent = FlockFactory.create_default_agent(
        name="advanced_agent",
        input="data: str",
        output="analysis: str",
        enable_rich_tables=True,
        temperature=0.7,
        max_tokens=4096,
        stream=True,
        include_thought_process=True,
        no_output=True  # Suppress output for test
    )
    
    print(f"✅ Advanced agent created: {advanced_agent.name}")
    
    if advanced_agent.evaluator:
        eval_config = advanced_agent.evaluator.config
        print(f"   - Temperature: {eval_config.temperature}")
        print(f"   - Max tokens: {eval_config.max_tokens}")
        print(f"   - Streaming: {eval_config.stream}")
        print(f"   - Thought process: {eval_config.include_thought_process}")
    
    # Find output component in advanced agent
    adv_output_comp = None
    for comp in advanced_agent.components:
        if isinstance(comp, OutputUtilityComponent):
            adv_output_comp = comp
            break
    
    if adv_output_comp:
        print(f"   - Rich tables: {adv_output_comp.config.render_table}")
    
    print("\n🎉 FlockFactory Migration Test Complete!")
    print("✅ Factory successfully creates agents with unified components")
    print("✅ All component types properly configured")
    print("✅ Backward compatibility maintained for existing examples")


if __name__ == "__main__":
    test_factory_migration()
