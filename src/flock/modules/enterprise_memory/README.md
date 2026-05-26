# Enterprise Memory Module

The **EnterpriseMemoryModule** brings durable, scalable memory to Flock agents by
combining a true vector store (Chroma) with a property-graph database
(Neo4j / Memgraph).  It is a drop‐in replacement for the default
`memory` module when you need:

* millions of memory chunks without exhausting RAM
* concurrent writers (many agents / processes / machines)
* rich concept-graph queries and visualisation

---
## How it works

| Concern              | Technology |
|--------------------- |------------|
| Vector similarity    | **Pinecone**, **Chroma**, **Azure Cognitive Search** |
| Concept graph        | **Cypher** database (Neo4j / Memgraph) |
| Embeddings           | `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Concept extraction   | Agent's LLM via DSPy signature |

* Each memory chunk is embedded and added to the Chroma collection.
* Concepts are extracted; duplicates are eliminated via case-insensitive
  and fuzzy matching (≥ 0.85 similarity).
* Memory nodes and `(:Memory)-[:MENTIONS]->(:Concept)` edges are merged
  into the graph DB in batched transactions.
* Optional: export a PNG of the concept graph after every update.

---
## Configuration options (`EnterpriseMemoryModuleConfig`)

```yaml
chroma_path: ./vector_store          # disk path if running embedded
chroma_host: null                    # host of remote Chroma server (optional)
chroma_port: 8000
chroma_collection: flock_memories    # collection name

# or Pinecone
vector_backend: pinecone
pinecone_api_key: <YOUR_KEY>
pinecone_env: gcp-starter
pinecone_index: flock-memories

# or Azure Cognitive Search
vector_backend: azure
azure_search_endpoint: https://<service>.search.windows.net
azure_search_key: <KEY>
azure_search_index_name: flock-memories

cypher_uri: bolt://localhost:7687
cypher_username: neo4j
cypher_password: password

similarity_threshold: 0.5            # for retrieval
max_results: 10
number_of_concepts_to_extract: 3
save_interval: 10                    # batch size before commit

export_graph_image: false            # set true to emit PNGs
graph_image_dir: ./concept_graphs    # where to store images
```

---
## Dependencies

Add the following to your project (examples with pip):

```bash
pip install chromadb>=0.4.20
pip install neo4j>=5.14.0
pip install sentence-transformers>=2.7.0
pip install matplotlib networkx     # only needed when export_graph_image = true
pip install pinecone-client         # if using Pinecone
pip install azure-search-documents  # if using Azure Search
```

You also need a running Neo4j **or** Memgraph instance.  The module uses
the Bolt protocol and Cypher `MERGE`, which works on both.

---
## Usage

```python
from flock.modules.enterprise_memory.enterprise_memory_module import (
    EnterpriseMemoryModule, EnterpriseMemoryModuleConfig,
)

agent.add_module(
    EnterpriseMemoryModule(
        name="enterprise_memory",
        config=EnterpriseMemoryModuleConfig(
            cypher_password=os.environ["NEO4J_PASSWORD"],
            export_graph_image=True,
        ),
    )
)
```

The rest of the agent code stays unchanged. 