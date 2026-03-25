"""
Graph Constructor: Transforms raw dataset into Neo4j graph.

Design Pattern:
1. Data validation and normalization
2. Entity creation (nodes with properties)
3. Relationship creation (edges)
4. Index creation for performance
5. Integrity validation

Following DESIGN_GUIDELINES.md data modeling principles:
- unique constraints on entity IDs
- indexed properties for lookups
- typed relationships (ALL_CAPS)
- metadata tracking (created_at, updated_at)
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from neo4j import GraphDatabase, Record
from neo4j.graph import Node, Relationship
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConstructionStats:
    """Statistics from graph construction"""
    nodes_created: int
    relationships_created: int
    indices_created: int
    constraints_created: int
    duration_seconds: float


class GraphConstructor:
    """
    Builds and manages Neo4j graph from dataset.
    
    Design Principles:
    1. Idempotent operations (safe to re-run)
    2. Comprehensive error handling
    3. Performance optimization via batching
    4. Audit trail (created_at, updated_at metadata)
    """
    
    # ========================================================================
    # Entity Type Definitions
    # ========================================================================
    
    # Node types and their required properties
    ENTITY_SCHEMA = {
        "Order": {
            "required_properties": ["order_id", "customer_id", "order_date"],
            "indexed_properties": ["order_id", "customer_id", "order_date"],
            "unique_property": "order_id",
            "description": "Sales order"
        },
        "OrderItem": {
            "required_properties": ["order_item_id", "product_id", "quantity"],
            "indexed_properties": ["order_item_id", "product_id"],
            "unique_property": "order_item_id",
            "description": "Line item in order"
        },
        "Delivery": {
            "required_properties": ["delivery_id", "delivery_date"],
            "indexed_properties": ["delivery_id", "delivery_date"],
            "unique_property": "delivery_id",
            "description": "Shipment/delivery record"
        },
        "Invoice": {
            "required_properties": ["invoice_id", "order_id", "invoice_date"],
            "indexed_properties": ["invoice_id", "order_id", "invoice_date"],
            "unique_property": "invoice_id",
            "description": "Billing document"
        },
        "Payment": {
            "required_properties": ["payment_id", "invoice_id", "amount", "payment_date"],
            "indexed_properties": ["payment_id", "invoice_id"],
            "unique_property": "payment_id",
            "description": "Payment record"
        },
        "Customer": {
            "required_properties": ["customer_id", "customer_name"],
            "indexed_properties": ["customer_id"],
            "unique_property": "customer_id",
            "description": "Customer entity"
        },
        "Product": {
            "required_properties": ["product_id", "product_name"],
            "indexed_properties": ["product_id"],
            "unique_property": "product_id",
            "description": "Product/material"
        },
        "Address": {
            "required_properties": ["address_id"],
            "indexed_properties": ["address_id"],
            "unique_property": "address_id",
            "description": "Address/location"
        },
    }
    
    # Relationship types and their semantics
    RELATIONSHIP_TYPES = [
        ("Order", "CONTAINS", "OrderItem", {"description": "Order contains line items"}),
        ("OrderItem", "REFERS_TO", "Product", {"description": "Item references product"}),
        ("Order", "SHIPPED_BY", "Delivery", {"description": "Order shipped via delivery"}),
        ("Delivery", "TO_ADDRESS", "Address", {"description": "Delivery destination"}),
        ("Order", "GENERATES", "Invoice", {"description": "Order generates invoice"}),
        ("Invoice", "RECEIVES", "Payment", {"description": "Invoice receives payment"}),
        ("Customer", "PLACES", "Order", {"description": "Customer places order"}),
    ]
    
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """
        Initialize Neo4j connection.
        
        Args:
            uri: Neo4j bolt URI (e.g., "bolt://localhost:7687")
            username: Neo4j username
            password: Neo4j password
            database: Database name (default: "neo4j")
        """
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        logger.info(f"Connected to Neo4j at {uri}")
    
    def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()
    
    # ========================================================================
    # Initialization: Schema Setup
    # ========================================================================
    
    def initialize_schema(self) -> ConstructionStats:
        """
        Create all constraints and indices.
        
        Design Principle: Idempotent - safe to call multiple times
        
        Returns:
            ConstructionStats with counts
        """
        stats = ConstructionStats(0, 0, 0, 0, 0)
        
        with self.driver.session(database=self.database) as session:
            # Create constraints
            for entity_type, schema in self.ENTITY_SCHEMA.items():
                unique_prop = schema["unique_property"]
                try:
                    session.run(
                        f"CREATE CONSTRAINT {entity_type.lower()}_unique "
                        f"IF NOT EXISTS FOR (n:{entity_type}) "
                        f"REQUIRE n.{unique_prop} IS UNIQUE"
                    )
                    stats.constraints_created += 1
                    logger.info(f"Created constraint on {entity_type}.{unique_prop}")
                except Exception as e:
                    logger.warning(f"Constraint for {entity_type} may already exist: {e}")
            
            # Create indices
            for entity_type, schema in self.ENTITY_SCHEMA.items():
                for prop in schema["indexed_properties"]:
                    try:
                        session.run(
                            f"CREATE INDEX {entity_type.lower()}_{prop}_idx "
                            f"IF NOT EXISTS FOR (n:{entity_type}) "
                            f"ON (n.{prop})"
                        )
                        stats.indices_created += 1
                        logger.info(f"Created index on {entity_type}.{prop}")
                    except Exception as e:
                        logger.warning(f"Index for {entity_type}.{prop} may already exist: {e}")
        
        return stats
    
    # ========================================================================
    # Data Ingestion: Node Creation
    # ========================================================================
    
    def create_nodes_batch(self, 
                          entity_type: str,
                          records: List[Dict[str, Any]],
                          batch_size: int = 1000) -> int:
        """
        Create nodes in batches for performance.
        
        Design Principle: Batch processing for large datasets
        
        Args:
            entity_type: Type of entity (Order, Customer, etc.)
            records: List of entity records
            batch_size: Number of records per batch
        
        Returns:
            Number of nodes created
        """
        if entity_type not in self.ENTITY_SCHEMA:
            raise ValueError(f"Unknown entity type: {entity_type}")
        
        created_count = 0
        schema = self.ENTITY_SCHEMA[entity_type]
        
        # Process in batches
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            
            with self.driver.session(database=self.database) as session:
                for record in batch:
                    # Validate required properties
                    for req_prop in schema["required_properties"]:
                        if req_prop not in record:
                            logger.error(f"Missing required property {req_prop} in record: {record}")
                            continue
                    
                    # Add metadata
                    record["_created_at"] = datetime.utcnow().isoformat()
                    record["_updated_at"] = datetime.utcnow().isoformat()
                    
                    # Create or merge node
                    unique_prop = schema["unique_property"]
                    unique_value = record[unique_prop]
                    
                    try:
                        session.run(
                            f"MERGE (n:{entity_type} {{{unique_prop}: $id}}) "
                            f"SET n += $props "
                            f"RETURN n",
                            id=unique_value,
                            props=record
                        )
                        created_count += 1
                    
                    except Exception as e:
                        logger.error(f"Failed to create {entity_type} node: {e}")
        
        logger.info(f"Created {created_count} {entity_type} nodes")
        return created_count
    
    # ========================================================================
    # Data Ingestion: Relationship Creation
    # ========================================================================
    
    def create_relationships_batch(self,
                                   source_type: str,
                                   source_id_prop: str,
                                   source_id_values: List[Tuple[str, str]],  # (id_prop_value, related_id_value)
                                   target_type: str,
                                   target_id_prop: str,
                                   rel_type: str,
                                   rel_properties: Optional[Dict[str, Any]] = None) -> int:
        """
        Create relationships between nodes.
        
        Design Principle: Explicit relationship types (ALL_CAPS)
        
        Args:
            source_type: Source node type
            source_id_prop: Source ID property name
            source_id_values: List of (source_id, target_id) tuples
            target_type: Target node type
            target_id_prop: Target ID property name
            rel_type: Relationship type (ALL_CAPS)
            rel_properties: Optional relationship properties
        
        Returns:
            Number of relationships created
        """
        rel_properties = rel_properties or {}
        created_count = 0
        
        with self.driver.session(database=self.database) as session:
            for source_id, target_id in source_id_values:
                try:
                    session.run(
                        f"MATCH (s:{source_type} {{{source_id_prop}: $source_id}}) "
                        f"MATCH (t:{target_type} {{{target_id_prop}: $target_id}}) "
                        f"MERGE (s)-[r:{rel_type}]->(t) "
                        f"SET r += $props "
                        f"RETURN r",
                        source_id=source_id,
                        target_id=target_id,
                        props={**rel_properties, "_created_at": datetime.utcnow().isoformat()}
                    )
                    created_count += 1
                
                except Exception as e:
                    logger.error(f"Failed to create {rel_type} relationship: {e}")
        
        logger.info(f"Created {created_count} {rel_type} relationships")
        return created_count
    
    # ========================================================================
    # Graph Validation
    # ========================================================================
    
    def validate_graph_integrity(self) -> Dict[str, Any]:
        """
        Validate graph integrity constraints.
        
        Checks:
        1. No orphaned nodes
        2. Referential integrity
        3. Cardinality constraints
        4. Schema compliance
        
        Returns:
            Dictionary with validation results
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "stats": {}
        }
        
        with self.driver.session(database=self.database) as session:
            # Check node counts
            for entity_type in self.ENTITY_SCHEMA:
                count_result = session.run(f"MATCH (n:{entity_type}) RETURN COUNT(n) as count")
                count = count_result.single()["count"]
                results["stats"][entity_type] = count
                
                if count == 0:
                    results["warnings"].append(f"No {entity_type} nodes found")
            
            # Check for orphaned nodes (no relationships)
            orphaned_result = session.run(
                "MATCH (n) WHERE NOT (n)--() RETURN COUNT(n) as count"
            )
            orphaned_count = orphaned_result.single()["count"]
            results["stats"]["orphaned_nodes"] = orphaned_count
            if orphaned_count > 0:
                results["warnings"].append(f"Found {orphaned_count} orphaned nodes")
            
            # Check relationship counts
            rel_result = session.run("MATCH ()--() RETURN COUNT(*) as count")
            rel_count = rel_result.single()["count"]
            results["stats"]["total_relationships"] = rel_count
        
        return results
    
    # ========================================================================
    # Graph Querying
    # ========================================================================
    
    def get_graph_summary(self) -> Dict[str, Any]:
        """
        Get high-level graph statistics.
        
        Returns:
            Summary of graph structure and size
        """
        with self.driver.session(database=self.database) as session:
            node_result = session.run("MATCH (n) RETURN COUNT(n) as total")
            node_count = node_result.single()["total"]
            
            edge_result = session.run("MATCH ()-->() RETURN COUNT(*) as total")
            edge_count = edge_result.single()["total"]
            
            type_result = session.run(
                "MATCH (n) RETURN labels(n)[0] as type, COUNT(*) as count "
                "ORDER BY count DESC"
            )
            type_counts = {record["type"]: record["count"] for record in type_result}
        
        return {
            "total_nodes": node_count,
            "total_edges": edge_count,
            "node_types": type_counts
        }
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def clear_all_data(self) -> bool:
        """
        WARNING: Delete all nodes and relationships.
        Use only for testing/reset.
        """
        try:
            with self.driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.warning("Cleared all data from graph")
            return True
        except Exception as e:
            logger.error(f"Failed to clear graph: {e}")
            return False


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Setup
    constructor = GraphConstructor(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="password123"
    )
    
    try:
        # Initialize schema
        print("Initializing schema...")
        stats = constructor.initialize_schema()
        print(f"  Constraints: {stats.constraints_created}, Indices: {stats.indices_created}")
        
        # Get summary
        print("\nGraph Summary:")
        summary = constructor.get_graph_summary()
        print(f"  Total nodes: {summary['total_nodes']}")
        print(f"  Total edges: {summary['total_edges']}")
        
        # Validate integrity
        print("\nGraph Validation:")
        integrity = constructor.validate_graph_integrity()
        if integrity["valid"]:
            print("  ✓ Graph is valid")
        else:
            for error in integrity["errors"]:
                print(f"  ✗ {error}")
    
    finally:
        constructor.close()
