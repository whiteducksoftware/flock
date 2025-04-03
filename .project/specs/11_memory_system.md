# Flock Memory System Specification

## Overview
The memory system provides agents with the ability to store, retrieve, and reason over past information. It enables contextual awareness, knowledge persistence, and semantic search capabilities. This specification defines the components and behavior of the memory system.

**Core Implementation:** `src/flock/modules/memory/`

## Core Components

### 1. MemoryModule

**Implementation:** `src/flock/modules/memory/memory_module.py`

**Purpose:**
Adds memory capabilities to Flock agents through the module extension system.

**Key Features:**
- Memory persistence across agent invocations
- Semantic search for relevant context
- Concept extraction and tracking
- Multiple memory retrieval strategies
- Automatic memory updating from agent interactions

**Configuration:**
- `folder_path`: Directory for memory storage
- `file_path`: Memory file location
- `similarity_threshold`: Threshold for semantic matching
- `max_length`: Maximum entry length before splitting
- `save_after_update`: Whether to save after each update
- `splitting_mode`: Strategy for splitting long memories
- `enable_read_only_mode`: Prevents memory updates
- `number_of_concepts_to_extract`: Concepts per memory entry

### 2. FlockMemoryStore

**Implementation:** `src/flock/modules/memory/memory_storage.py`

**Purpose:**
Provides the underlying storage and retrieval mechanisms for agent memories.

**Key Features:**
- JSON file-based persistence
- Embedding-based semantic search
- Concept-based retrieval
- Exact match retrieval
- Automatic embedding computation
- Deduplication of similar memories

**API:**
- `load_from_file(filename)`: Load memory from file
- `save_to_file(filename)`: Save memory to file
- `add(content, concepts)`: Add new memory entry
- `retrieve(embedding, concepts, threshold)`: Retrieve similar memories
- `exact_match(query)`: Find exact matches in memory

### 3. MemoryMappingParser

**Implementation:** `src/flock/modules/memory/memory_parser.py`

**Purpose:**
Parses memory mapping configurations to determine retrieval strategies.

**Key Features:**
- Support for semantic and exact-match retrieval
- Configuration-based memory operations
- Flexible memory mapping syntax

**API:**
- `parse(mapping_string)`: Convert string configuration to memory operations

## Memory Integration

### Module Integration
- The memory module hooks into agent lifecycle events:
  - `initialize`: Set up memory store
  - `pre_evaluate`: Add relevant memories to context
  - `post_evaluate`: Extract and store new memories
  - `terminate`: Ensure memory is saved

### Agent Context Enhancement
- Memory is injected into the agent's context during `pre_evaluate`
- The agent's input is extended to include a context field
- Memory is automatically updated with new information during `post_evaluate`

## Memory Operations

### 1. Memory Retrieval
- **Semantic Retrieval**: Find memories semantically related to the input
- **Exact Match**: Find memories that exactly match query terms
- **Concept-Based**: Find memories related to extracted concepts

### 2. Memory Storage
- **Chunking**: Large memories are split using various strategies
- **Concept Extraction**: Key concepts are identified and stored
- **Embedding Computation**: Semantic embeddings are calculated for retrieval

### 3. Memory Processing
- **Summarization Mode**: Condense long memories into summaries
- **Semantic Splitting**: Split memories by semantic content
- **Character Splitting**: Split memories by character count

## Design Principles

1. **Contextual Awareness**:
   - Memory provides additional context to agent decisions
   - Relevant memories are automatically retrieved
   - Concept connections provide semantic understanding

2. **Persistence**:
   - Memory persists across agent invocations
   - File-based storage ensures durability
   - Configurable saving strategies

3. **Semantic Intelligence**:
   - Embedding-based retrieval for similar concepts
   - Concept extraction for better understanding
   - Multiple retrieval strategies for flexibility

4. **Performance**:
   - Configurable thresholds for memory relevance
   - Memory chunking for manageable pieces
   - Optional read-only mode for query-intensive workflows

## Implementation Requirements

1. Embedding capability must be available for semantic operations
2. File storage locations must be configurable
3. Memory operations must be thread-safe
4. Memory persistence should be reliable
5. Module lifecycle integration must be properly implemented 