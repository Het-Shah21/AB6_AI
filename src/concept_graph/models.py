from pydantic import BaseModel
from typing import Any


class ConceptNode(BaseModel):
    id: str
    name: str
    description: str = ""
    domain: str = ""
    difficulty: float = 0.5
    source_type: str = ""
    source_id: str = ""


class ConceptEdge(BaseModel):
    from_concept_id: str
    to_concept_id: str
    edge_type: str = "prerequisite"
    weight: float = 1.0
    source: str = "auto"


class ConceptMapping(BaseModel):
    concept_id: str
    entity_type: str
    entity_id: str
    relevance: float = 1.0


class ConceptGraph(BaseModel):
    nodes: dict[str, ConceptNode] = {}
    edges: list[ConceptEdge] = []


class ExtractedConcept(BaseModel):
    id: str
    name: str
    domain: str
    difficulty: float = 0.5
