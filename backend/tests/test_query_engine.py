from app.guardrails import Guardrails
from app.query_engine import QueryEngine


def test_query_engine_template_contains_expected_keywords():
    guardrails = Guardrails()
    engine = QueryEngine(
        llm_provider=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password123",
        guardrails=guardrails,
    )

    cypher = engine._template_cypher("Which products are in the most orders?")
    assert "Product" in cypher
    assert "REFERS_TO" in cypher


def test_translate_to_cypher_uses_template_when_llm_disabled():
    guardrails = Guardrails()
    engine = QueryEngine(
        llm_provider=None,
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password123",
        guardrails=guardrails,
    )

    cypher = engine._translate_to_cypher("Trace order ORD-001 through delivery to invoice")
    assert "MATCH" in cypher
    assert ("Order" in cypher or "Delivery" in cypher)

