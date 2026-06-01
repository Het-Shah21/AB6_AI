# Phase 4 — Concept Graph: System Design Diagrams

Phase 4 builds the **knowledge graph** of robotics concepts. The ORIENT node
later uses this graph to reason about prerequisite gaps when a student
struggles.

---

## 4.1 — Concept Graph Overview

```mermaid
flowchart LR
    subgraph CT["Curriculum Source"]
        VS["Video titles<br>Challenge descriptions"]
    end

    subgraph P4["Phase 4 Pipeline"]
        LLM["LLM extract<br>(builder.py)"]
        EMB["OpenAI embedding<br>(embeddings.py)"]
        DED["Deduplicate<br>(cosine sim > 0.92)"]
        EDGE["Infer edges<br>(LLM pairwise)"]
    end

    subgraph DB["PostgreSQL (ab6_learning_data)"]
        CN[("ai_concepts<br>+ vector(1536)")]
        CE[("ai_concept_edges")]
        CM[("ai_concept_mappings<br>(videos, challenges)")]
    end

    VS --> LLM
    LLM --> EMB
    EMB --> DED
    DED --> EDGE
    DED -->|INSERT| CN
    EDGE -->|INSERT| CE
    EMB -->|"update embedding"| CN
    CM -->|"external links"| CN
```

---

## 4.2 — Build Pipeline (Detailed)

```mermaid
flowchart TB
    A["video_titles[]"] --> B["build_concept_graph(titles)"]
    B --> C["build prompt<br>CONCEPT_EXTRACTION_PROMPT"]
    C --> D["llm.reasoning.ainvoke()"]
    D --> E["_parse_llm_json()"]
    E --> F["ConceptNode[]"]
    F --> G["generate_embeddings_batch()<br>(OpenAI text-embedding-3-small)"]
    G --> H["_deduplicate_concepts<br>(threshold=0.92)"]
    H --> I["UPSERT into ai_concepts<br>(ON CONFLICT id DO UPDATE)"]
    I --> J["_infer_edges<br>(pairwise LLM call)"]
    J --> K["INSERT INTO ai_concept_edges<br>(ON CONFLICT DO NOTHING)"]
    K --> L["sess.commit()"]
    L --> M["{concepts_count, edges_count}"]
```

---

## 4.3 — Deduplication Threshold

```mermaid
flowchart LR
    A["New concept embedding"] --> B{{"cosine_sim > 0.92<br>vs any existing?"}}
    B -- Yes --> DROP["Drop as duplicate"]
    B -- No --> KEEP["Keep as new concept"]
```

> 0.92 is empirically tuned. Concept descriptions above this threshold are
> almost always the same concept phrased differently.

---

## 4.4 — Recursive CTE Prerequisite Walk

`get_prerequisite_chain()` walks the prerequisite DAG to arbitrary depth
using a recursive CTE. Same pattern is reused by `find_unmastered_prerequisites`.

```mermaid
flowchart TB
    ROOT["target concept_id"]
    ROOT --> L1["level 1: direct prerequisites"]
    L1 --> L2["level 2: prerequisites of prerequisites"]
    L2 --> L3["level N: keep walking until no more edges"]
    L3 --> OUT["ordered list<br>(deepest prerequisites first)"]

    SQL["WITH RECURSIVE chain AS (<br>  anchor: edges where to_concept_id = :cid<br>  UNION ALL<br>  recursive: edges joining on from_concept_id<br>)<br>SELECT ... ORDER BY level DESC"]
    ROOT -. "anchors" .- SQL
    SQL -. "iterates" .- L2
    SQL -. "iterates" .- L3
```

---

## 4.5 — Semantic Search with pgvector

```mermaid
flowchart LR
    Q["user query string"] --> EMB["generate_embedding()<br>text-embedding-3-small"]
    EMB -->|"1536-dim vector"| SQL["SELECT id, name, description,<br>embedding &lt;=&gt; :q AS distance<br>FROM ai_concepts<br>WHERE embedding IS NOT NULL<br>ORDER BY distance<br>LIMIT :top_k"]
    SQL -->|cosine distance| PG[("pgvector HNSW index<br>O(log n) search")]
    PG --> RES["Top-k concepts"]
    RES --> API["/api/v1/ai/concepts/search"]
```

The `<=>` operator is pgvector's **cosine distance**. With an HNSW index this
runs in milliseconds even on millions of vectors.

---

## 4.6 — Data Model Detail

```mermaid
erDiagram
    CONCEPT ||--o{ EDGE : "from / to"
    CONCEPT ||--o{ MAPPING : "linked to"
    CONCEPT {
        string id PK
        string name
        string domain
        float difficulty
        vector embedding "1536-dim"
        string source_type
    }
    EDGE {
        string from_concept_id FK
        string to_concept_id FK
        string edge_type "prerequisite"
        float weight
    }
    MAPPING {
        string concept_id FK
        string entity_type "video / challenge"
        string entity_id
        float relevance
    }
```

Note: ORM columns differ from the Pydantic concept-graph models — ORM
columns live in `src/db/models/ai_concept*.py`, while graph-domain models
live in `src/concept_graph/models.py`.

---

## 4.7 — How the OODA Agent Uses the Graph

```mermaid
sequenceDiagram
    autonumber
    participant ORIENT
    participant Q as queries.py
    participant PG as PostgreSQL
    participant DECIDE

    ORIENT->>Q: find_unmastered_prerequisites(target, mastered)
    Q->>PG: recursive CTE
    PG-->>Q: chain[]
    Q-->>ORIENT: unmastered[]
    ORIENT->>ORIENT: enrich diagnosis with missing prereqs
    ORIENT-->>DECIDE: diagnosed_struggles = target ∪ unmastered

    Note over DECIDE: For each struggle, pick intervention<br>via WisdomRepo (Phase 6)
```

---

## 4.8 — Phase 4 Component Map

```mermaid
flowchart LR
    subgraph P4["src/concept_graph/"]
        M["models.py<br>(ConceptNode, ConceptEdge, ConceptGraph, ExtractedConcept)"]
        E["embeddings.py<br>(generate / batch / cosine)"]
        B["builder.py<br>(build_concept_graph)"]
        Q["queries.py<br>(CTE + helpers)"]
    end
    subgraph EXT["External"]
        LLM["LLM provider<br>(reasoning + primary)"]
        OAI["OpenAI embeddings<br>text-embedding-3-small"]
        PG[("PostgreSQL<br>pgvector")]
    end
    M --> B
    E --> B
    B --> LLM
    B --> OAI
    B --> PG
    Q --> PG
    Q --> ORIENT["orient.py (Phase 5)"]
```
