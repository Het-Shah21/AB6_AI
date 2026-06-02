import pytest

from legacy.concept_graph.embeddings import cosine_similarity
from legacy.concept_graph.builder import _deduplicate_concepts, _parse_llm_json
from legacy.concept_graph.models import ConceptNode


def test_cosine_similarity_identical():
    v = [1.0, 0.0, 0.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 0.001


def test_cosine_similarity_orthogonal():
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    assert abs(cosine_similarity(v1, v2)) < 0.001


def test_parse_llm_json_valid():
    raw = '{"key": "value"}'
    assert _parse_llm_json(raw) == []


def test_parse_llm_json_array():
    raw = '[{"id": "test", "name": "Test"}]'
    result = _parse_llm_json(raw)
    assert len(result) == 1
    assert result[0]["id"] == "test"


def test_deduplicate_empty():
    result = _deduplicate_concepts([], [], 0.92)
    assert result == []


def test_deduplicate_single():
    c = ConceptNode(id="a", name="A", domain="test")
    result = _deduplicate_concepts([c], [[1.0, 0.0]], 0.92)
    assert len(result) == 1
