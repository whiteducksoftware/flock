# Flock Architecture

## Package Structure

```mermaid
graph TD
    flock[flock]
    agents[agents]
    core[core]
    themes[themes]
    workflow[workflow]
    
    flock --> agents
    flock --> core
    flock --> themes
    flock --> workflow
    
    core --> context[context]
    core --> execution[execution]
    core --> logging[logging]
    core --> mixin[mixin]
    core --> registry[registry]
    core --> tools[tools]
    core --> util[util]
    
    agents --> batch[batch_agent]
    agents --> loop[loop_agent]
    agents --> trigger[trigger_agent]
    agents --> user[user_agent]
```

## Core Components

```mermaid
classDiagram
    class Flock {
        +agents: dict
        +registry: Registry
        +context: FlockContext
        +model: str
        +local_debug: bool
        +add_agent(agent)
        +add_tool(tool_name, tool)
        +run_async(start_agent, input)
    }
    
    class FlockAgent {
        +name: str
        +model: str
        +description: str
        +input: str
        +output: str
        +tools: list
        +use_cache: bool
        +hand_off: str|callable
        +initialize(inputs)
        +terminate(inputs, result)
        +on_error(error, inputs)
        +run(inputs)
        +run_temporal(inputs)
    }
    
    class Registry {
        +register_agent(agent)
        +register_tool(tool_name, tool)
        +get_agent(name)
    }
    
    class FlockContext {
        +state: dict
        +history: list
        +agent_definitions: list
        +add_agent_definition()
        +get_variable()
    }

    Flock --> "1" Registry : has
    Flock --> "1" FlockContext : has
    Flock --> "*" FlockAgent : manages
    FlockAgent --> "1" FlockContext : uses
```

## Agent Types

```mermaid
classDiagram
    class FlockAgent {
        <<abstract>>
        +name: str
        +model: str
        +input: str
        +output: str
        +tools: list
        +run(inputs)
    }
    
    class BatchAgent {
        +iter_input: str
        +batch_size: int
        +run(context)
        +run_temporal(context)
    }
    
    class LoopAgent {
        +condition: str
        +run(context)
    }
    
    class TriggerAgent {
        +trigger_condition: str
        +run(context)
    }
    
    class UserAgent {
        +interface_type: str
        +run(context)
    }
    
    FlockAgent <|-- BatchAgent
    FlockAgent <|-- LoopAgent
    FlockAgent <|-- TriggerAgent
    FlockAgent <|-- UserAgent
```

## Execution Flow

```mermaid
sequenceDiagram
    participant Client
    participant Flock
    participant FlockAgent
    participant Registry
    participant Context
    participant LLM
    
    Client->>Flock: run_async(agent, input)
    Flock->>Registry: get_agent(name)
    Registry-->>Flock: agent instance
    
    Flock->>Context: initialize_context(agent, input)
    
    Flock->>FlockAgent: run(inputs)
    activate FlockAgent
    
    FlockAgent->>FlockAgent: initialize(inputs)
    FlockAgent->>FlockAgent: _evaluate(inputs)
    
    FlockAgent->>LLM: process with tools/prompts
    LLM-->>FlockAgent: response
    
    FlockAgent->>FlockAgent: terminate(inputs, result)
    FlockAgent-->>Flock: result
    deactivate FlockAgent
    
    Flock-->>Client: final result
```

This architecture documentation shows the key components and relationships in the Flock framework:

1. **Package Structure**: Shows the main modules and their organization
2. **Core Components**: Illustrates the relationships between the main classes
3. **Agent Types**: Shows the inheritance hierarchy of different agent types
4. **Execution Flow**: Demonstrates the sequence of operations during agent execution

## Component Relations

```mermaid
graph TD
    subgraph Client Application
        client[Client Code]
    end

    subgraph Flock Framework
        orchestrator[Flock Orchestrator]
        registry[Agent Registry]
        context[Context Manager]
        
        subgraph Agents
            base[FlockAgent Base]
            batch[BatchAgent]
            loop[LoopAgent]
            trigger[TriggerAgent]
            user[UserAgent]
        end
        
        subgraph Execution
            local[Local Executor]
            temporal[Temporal Executor]
        end
        
        subgraph Core Services
            logging[Logging System]
            tools[Tool Registry]
            formatter[Output Formatters]
        end
    end

    subgraph External Services
        llm[Language Models]
        temporal_server[Temporal Server]
    end

    %% Client interactions
    client --> orchestrator
    
    %% Orchestrator relations
    orchestrator --> registry
    orchestrator --> context
    orchestrator --> local
    orchestrator --> temporal
    
    %% Agent relations
    base --> tools
    base --> logging
    base --> formatter
    batch --> base
    loop --> base
    trigger --> base
    user --> base
    
    %% Execution relations
    local --> llm
    temporal --> temporal_server
    temporal_server --> llm
    
    %% Registry relations
    registry --> base
    registry --> tools

    %% Style
    classDef default fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef external fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef core fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px;
    
    class llm,temporal_server external;
    class orchestrator,registry,context,base,local,temporal core;
```

Key architectural features:

- **Declarative Design**: Agents are defined by their inputs/outputs rather than explicit prompts
- **Modular Structure**: Clear separation between core components, agents, and workflow
- **Extensible**: Support for custom agents, tools, and execution environments
- **Production Ready**: Built-in support for both local debugging and Temporal workflow execution
