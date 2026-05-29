# Concept Graph

## Overview
The concept graph represents the robotics curriculum as a directed acyclic graph (DAG) of atomic concepts with prerequisite relationships. It enables the agent to identify knowledge gaps and recommend optimal learning paths.

## Auto-Construction Pipeline

1. **Extract** — Pull video titles and challenge metadata from database
2. **LLM Tag** — Send batches to LLM to extract atomic concepts
3. **Embed** — Generate OpenAI embeddings for semantic search
4. **Deduplicate** — Merge highly similar concepts (cosine > 0.92)
5. **Infer Edges** — Use LLM to determine prerequisite relationships
6. **Validate** — Ensure graph is a DAG
7. **Map** — Link concepts back to source videos and challenges

## Schema

- `ai_concepts` — Concept nodes with pgvector embeddings
- `ai_concept_edges` — Prerequisite/related edges between concepts
- `ai_concept_mappings` — Links concepts to videos and challenges

## Queries

- Prerequisite chain (recursive CTE)
- Learning path (ordered prerequisites)
- Semantic search (pgvector cosine distance)
- Unmastered prerequisite detection
