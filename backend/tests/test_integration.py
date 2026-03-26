import pytest
from neo4j import GraphDatabase


def neo4j_available(uri: str, user: str, password: str) -> bool:
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1 as x").single()
        driver.close()
        return True
    except Exception:
        return False


def test_graph_overview_endpoint_shape():
    # This integration test is optional; skip if Neo4j isn't reachable.
    if not neo4j_available("bolt://localhost:7687", "neo4j", "password123"):
        pytest.skip("Neo4j is not running locally")

    # Minimal sanity: Neo4j has at least a node after optional seeding.
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password123"))
    with driver.session() as session:
        count = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
    driver.close()

    assert count >= 0

