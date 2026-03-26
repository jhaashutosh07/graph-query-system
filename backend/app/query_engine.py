"""
Query Engine: Translates natural language to Cypher and executes graph queries.

Design Pattern:
1. User query → Guardrails check → LLM translation → Cypher execution → Response grounding
2. Few-shot prompting for accurate translation
3. Caching of common query patterns
4. Fallback to template queries on LLM failure

Following DESIGN_GUIDELINES.md LLM integration principles:
- Chain-of-thought prompting
- Response grounding in data
- Query result validation
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
from enum import Enum
from abc import ABC, abstractmethod

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class QueryComplexity(str, Enum):
    """Query complexity classification"""
    SIMPLE = "simple"          # Single entity lookup
    MODERATE = "moderate"       # Join 2-3 tables
    COMPLEX = "complex"         # Multi-hop or aggregation


class QueryExecutor:
    """
    Executes Cypher queries against Neo4j.
    
    Design Pattern: Wrapper around Neo4j driver with safety checks
    """
    
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """Initialize Neo4j connection"""
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        self.query_timeout = 5000  # milliseconds
    
    def execute_cypher(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute Cypher query with safety checks.
        
        Args:
            query: Cypher query string
            params: Query parameters
        
        Returns:
            List of result records
        """
        params = params or {}
        
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run(query, params)
                records = [dict(record) for record in result]
                logger.info(f"Query returned {len(records)} records")
                return records
        
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()


class FewShotExamples:
    """
    Collection of few-shot examples for LLM prompting.
    
    Core Design Principle: Few-shot examples drastically improve LLM accuracy
    on structured query generation. Examples should cover:
    1. Simple lookups
    2. Aggregations
    3. Path tracing
    4. Finding anomalies
    """
    
    EXAMPLES = [
        {
            "nl": "Which products are associated with the highest number of billing documents?",
            "cypher": """
MATCH (p:Product)<-[:REFERS_TO]-(oi:OrderItem)-[:IN]-(o:Order)
MATCH (o)-[:GENERATES]->(i:Invoice)
WITH p.product_id as pid, p.product_name as pname, COUNT(DISTINCT i) as invoice_count
RETURN pname, invoice_count
ORDER BY invoice_count DESC
LIMIT 10
            """,
            "explanation": "Find product with most invoices by traversing OrderItem → Product and Order → Invoice"
        },
        {
            "nl": "Trace the full flow of billing document INV-001",
            "cypher": """
MATCH (inv:Invoice {invoice_id: 'INV-001'})
OPTIONAL MATCH (inv)<-[:GENERATES]-(o:Order)
OPTIONAL MATCH (o)-[:SHIPPED_BY]->(d:Delivery)
OPTIONAL MATCH (inv)<-[:RECEIVES]-(p:Payment)
RETURN {
  invoice: inv,
  order: o,
  delivery: d,
  payment: p
} as flow
            """,
            "explanation": "Use OPTIONAL MATCH to build complete flow: Invoice ← Order → Delivery, Invoice → Payment"
        },
        {
            "nl": "Find sales orders that are delivered but not billed",
            "cypher": """
MATCH (o:Order)-[:SHIPPED_BY]->(d:Delivery)
WHERE NOT (o)-[:GENERATES]->(:Invoice)
RETURN o.order_id as order_id, o.customer_id, o.order_date, d.delivery_date
            """,
            "explanation": "Use WHERE NOT to find missing invoices for delivered orders (anomaly detection)"
        },
        {
            "nl": "Identify customers with the most pending orders",
            "cypher": """
MATCH (c:Customer)-[:PLACES]->(o:Order)
WHERE o.status IN ['pending', 'in_progress']
WITH c.customer_id as cid, c.customer_name as cname, COUNT(o) as pending_count
RETURN cname, pending_count
ORDER BY pending_count DESC
LIMIT 10
            """,
            "explanation": "Filter by status, aggregate by customer, order by count"
        },
        {
            "nl": "Get all items from order ORD-123",
            "cypher": """
MATCH (o:Order {order_id: 'ORD-123'})-[:CONTAINS]->(oi:OrderItem)
OPTIONAL MATCH (oi)-[:REFERS_TO]->(p:Product)
RETURN oi.order_item_id, p.product_name, oi.quantity, p.price
            """,
            "explanation": "Single order lookup with related items and products"
        },
    ]
    
    @staticmethod
    def get_few_shot_prompt() -> str:
        """Generate few-shot prompt for LLM"""
        prompt = "You are a Neo4j Cypher query translator for a business database.\n\n"
        prompt += "SCHEMA:\n"
        prompt += "- Entities: Order, OrderItem, Delivery, Invoice, Payment, Customer, Product, Address\n"
        prompt += "- Relationships: CONTAINS, REFERS_TO, SHIPPED_BY, TO_ADDRESS, GENERATES, RECEIVES, PLACES\n\n"
        
        prompt += "EXAMPLES:\n"
        for i, example in enumerate(FewShotExamples.EXAMPLES, 1):
            prompt += f"{i}. Natural Language: {example['nl']}\n"
            prompt += f"   Cypher: {example['cypher'].strip()}\n"
            prompt += f"   Explanation: {example['explanation']}\n\n"
        
        return prompt
    
    @staticmethod
    def get_schema_description() -> str:
        """Get detailed schema description for context"""
        return """
DATABASE SCHEMA:

Nodes:
- Order: order_id, customer_id, order_date, total_amount, status
- OrderItem: order_item_id, product_id, quantity, unit_price
- Delivery: delivery_id, delivery_date, ship_date, destination_address
- Invoice: invoice_id, order_id, invoice_date, total_amount, status
- Payment: payment_id, invoice_id, amount, payment_date, payment_method
- Customer: customer_id, customer_name, email, country
- Product: product_id, product_name, category, price, stock
- Address: address_id, street, city, country, postal_code

Relationships:
- Order -[:CONTAINS]-> OrderItem (one order contains many items)
- OrderItem -[:REFERS_TO]-> Product (item references a product)
- Order -[:SHIPPED_BY]-> Delivery (order is shipped via delivery)
- Delivery -[:TO_ADDRESS]-> Address (delivery goes to address)
- Order -[:GENERATES]-> Invoice (order generates invoice)
- Invoice -[:RECEIVES]-> Payment (invoice receives payment)
- Customer -[:PLACES]-> Order (customer places order)

KEY QUERY PATTERNS:
1. Lookups: MATCH (entity {id_field: value}) RETURN entity
2. Aggregations: MATCH ... WITH entity, COUNT(*) as count RETURN ... ORDER BY count
3. Path finding: MATCH p=(start)-[*..n]-(end) to find paths with depth control
4. Anomalies: WHERE NOT (entity)-[:RELATIONSHIP]->(...) to find missing relationships
"""


class QueryEngine:
    """
    Main query engine: NL → Cypher → Execution → Response.
    
    Design Pattern:
    1. Validate query with guardrails
    2. Translate NL to Cypher (with few-shot examples)
    3. Execute Cypher query
    4. Ground response in data
    5. Extract referenced entities
    """
    
    def __init__(self, 
                 llm_provider,  # e.g., Google Gemini client
                 neo4j_uri: str,
                 neo4j_user: str,
                 neo4j_password: str,
                 guardrails,  # Guardrails validator
                 neo4j_database: str = "neo4j",
                 cache_store=None):  # Optional cache (Redis, etc.)
        
        self.llm = llm_provider
        self.executor = QueryExecutor(
            neo4j_uri,
            neo4j_user,
            neo4j_password,
            database=neo4j_database,
        )
        self.guardrails = guardrails
        self.cache = cache_store  # For caching responses
        
        # Initialize prompt templates
        self.few_shot_prompt = FewShotExamples.get_few_shot_prompt()
        self.schema_description = FewShotExamples.get_schema_description()
    
    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Main query processing pipeline.
        
        Returns:
            {
                "status": "success" | "rejected" | "error",
                "answer": str,
                "referenced_entities": list,
                "cypher_query": str (debug),
                "execution_time_ms": float
            }
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Guardrails check
            guardrail_result = self.guardrails.check_query(user_query)
            if not guardrail_result.is_valid:
                return {
                    "status": "rejected",
                    "answer": self.guardrails.get_rejection_message(guardrail_result),
                    "referenced_entities": [],
                    "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            
            # Step 2: Check cache (if available)
            if self.cache:
                cached_response = self.cache.get(f"query:{user_query}")
                if cached_response:
                    logger.info("Cache hit")
                    return cached_response
            
            # Step 3: Translate to Cypher
            cypher_query = self._translate_to_cypher(user_query)
            logger.info(f"Generated Cypher: {cypher_query}")
            
            # Step 4: Validate Cypher safety
            is_safe, safety_msg = self.guardrails.validate_cypher_query(cypher_query)
            if not is_safe:
                logger.warning(f"Cypher validation failed: {safety_msg}")
                return {
                    "status": "error",
                    "answer": "Generated query failed safety validation",
                    "referenced_entities": [],
                    "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            
            # Step 5: Execute query
            results = self.executor.execute_cypher(cypher_query)
            
            if not results:
                return {
                    "status": "success",
                    "answer": "No data found matching your query.",
                    "referenced_entities": [],
                    "cypher_query": cypher_query,
                    "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            
            # Step 6: Generate natural language response (data-grounded)
            nl_response = self._generate_response(user_query, results)
            
            # Step 7: Extract referenced entities
            entities = self._extract_entities(results)
            
            response = {
                "status": "success",
                "answer": nl_response,
                "referenced_entities": entities,
                "cypher_query": cypher_query,  # Debug
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
            }
            
            # Step 8: Cache response
            if self.cache:
                self.cache.set(f"query:{user_query}", response, ttl=3600)
            
            return response
        
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "status": "error",
                "answer": "An error occurred while processing your query.",
                "referenced_entities": [],
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
            }
    
    # ========================================================================
    # Step 3: LLM-based Cypher Translation
    # ========================================================================
    
    def _translate_to_cypher(self, user_query: str) -> str:
        """
        Translate natural language query to Cypher using LLM.
        
        Design Pattern: Few-shot prompting with schema context
        """
        prompt = f"""{self.few_shot_prompt}

{self.schema_description}

USER QUERY: {user_query}

INSTRUCTIONS:
1. Generate a valid Cypher query that answers the user's question
2. Use appropriate MATCH patterns and WHERE clauses
3. Use aggregations (COUNT, SUM, AVG) only when needed
4. Limit results to 100 rows
5. Do NOT use DELETE, DROP, or ALTER operations
6. Return ONLY the Cypher query code, no explanations

CYPHER QUERY:
        """
        
        if not self.llm:
            return self._template_cypher(user_query)

        try:
            response = self.llm.generate_content(prompt)
            cypher = response.text.strip()
            
            # Clean up code block markers if present
            if cypher.startswith("```"):
                cypher = "\n".join(cypher.split("\n")[1:-1])
            
            return cypher
        
        except Exception as e:
            logger.error(f"LLM translation failed: {e}")
            return self._template_cypher(user_query)
    
    # ========================================================================
    # Step 6: Response Generation (Data-Grounded)
    # ========================================================================
    
    def _generate_response(self, user_query: str, results: List[Dict]) -> str:
        """
        Generate natural language response grounded in data.
        
        Design Principle: Response MUST cite actual data, not hallucinate
        """
        # Format results as readable text
        results_text = self._format_results(results)
        
        prompt = f"""You are a business data analyst. Answer the user's question based ONLY on the provided data.

USER QUESTION: {user_query}

DATA RESULTS:
{results_text}

INSTRUCTIONS:
1. Answer directly and concisely (2-3 sentences)
2. Use specific numbers and names from the data
3. Do NOT add information not in the results
4. If results are complex, summarize key findings
5. Never say you're uncertain - the data is authoritative

ANSWER:
        """
        
        if not self.llm:
            return self._format_results(results)

        try:
            response = self.llm.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return self._format_results(results)  # Fallback: return formatted data
    
    # ========================================================================
    # Step 7: Entity Extraction
    # ========================================================================
    
    def _extract_entities(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """
        Extract entities referenced in results for UI highlighting.
        
        Returns:
            List of {id, type, name} dicts for graph highlighting
        """
        entities = []
        id_fields = {
            "order_id": "Order",
            "customer_id": "Customer",
            "product_id": "Product",
            "invoice_id": "Invoice",
            "delivery_id": "Delivery",
        }
        
        for result in results:
            for field, entity_type in id_fields.items():
                if field in result:
                    entities.append({
                        "id": result[field],
                        "type": entity_type,
                        "name": result.get(f"{entity_type.lower()}_name", result[field])
                    })
        
        return list({e["id"]: e for e in entities}.values())  # Deduplicate
    
    # ========================================================================
    # Utility Methods
    # ========================================================================
    
    def _format_results(self, results: List[Dict]) -> str:
        """Format query results as readable text"""
        if not results:
            return "No results"
        
        if len(results) == 1:
            return json.dumps(results[0], indent=2)
        
        # Multiple results: show as table-like format
        lines = []
        for record in results[:20]:  # Limit display
            lines.append(str(record))
        
        if len(results) > 20:
            lines.append(f"... and {len(results) - 20} more results")
        
        return "\n".join(lines)

    def _template_cypher(self, user_query: str) -> str:
        """Fallback Cypher templates when LLM is unavailable."""
        q = user_query.lower()

        # Best-effort ID extraction for templates (hardcoded Cypher; no params used)
        import re

        order_id_match = re.search(r"\b(ORD[-_a-z0-9]+)\b", user_query, flags=re.IGNORECASE)
        invoice_id_match = re.search(r"\b(INV[-_a-z0-9]+)\b", user_query, flags=re.IGNORECASE)
        delivery_id_match = re.search(r"\b(DEL[-_a-z0-9]+)\b", user_query, flags=re.IGNORECASE)

        if "customer" in q and ("most" in q or "top" in q) and "order" in q:
            return """
MATCH (c:Customer)-[:PLACES]->(o:Order)
WITH c.customer_id as customer_id, c.customer_name as customer_name, COUNT(o) as order_count
RETURN customer_id, customer_name, order_count
ORDER BY order_count DESC
LIMIT 20
            """.strip()

        if "product" in q and ("most" in q or "top" in q) and "order" in q:
            return """
MATCH (o:Order)-[:CONTAINS]->(oi:OrderItem)-[:REFERS_TO]->(p:Product)
WITH p.product_id as product_id, p.product_name as product_name, COUNT(DISTINCT o) as order_count
RETURN product_id, product_name, order_count
ORDER BY order_count DESC
LIMIT 20
            """.strip()

        if ("trace" in q or "flow" in q or "path" in q) and "order" in q and order_id_match:
            oid = order_id_match.group(1)
            return f"""
MATCH (o:Order {{order_id: '{oid}'}})
OPTIONAL MATCH (o)-[:SHIPPED_BY]->(d:Delivery)
OPTIONAL MATCH (o)-[:GENERATES]->(i:Invoice)
OPTIONAL MATCH (i)-[:RECEIVES]->(p:Payment)
RETURN {{
  order: o,
  delivery: d,
  invoice: i,
  payment: p
}} as flow
            """.strip()

        if ("trace" in q or "flow" in q or "path" in q) and "invoice" in q and invoice_id_match:
            iid = invoice_id_match.group(1)
            return f"""
MATCH (inv:Invoice {{invoice_id: '{iid}'}})
OPTIONAL MATCH (inv)<-[:GENERATES]-(o:Order)
OPTIONAL MATCH (o)-[:SHIPPED_BY]->(d:Delivery)
OPTIONAL MATCH (inv)-[:RECEIVES]->(p:Payment)
RETURN {{
  invoice: inv,
  order: o,
  delivery: d,
  payment: p
}} as flow
            """.strip()

        if ("trace" in q or "flow" in q or "path" in q) and "delivery" in q and delivery_id_match:
            did = delivery_id_match.group(1)
            return f"""
MATCH (d:Delivery {{delivery_id: '{did}'}})
OPTIONAL MATCH (o:Order)-[:SHIPPED_BY]->(d)
OPTIONAL MATCH (o)-[:GENERATES]->(i:Invoice)
OPTIONAL MATCH (i)-[:RECEIVES]->(p:Payment)
RETURN {{
  delivery: d,
  order: o,
  invoice: i,
  payment: p
}} as flow
            """.strip()

        if "delivered" in q and "not" in q and ("invoice" in q or "bill" in q):
            return """
MATCH (o:Order)-[:SHIPPED_BY]->(d:Delivery)
WHERE NOT (o)-[:GENERATES]->(:Invoice)
RETURN o.order_id as order_id, o.status as status, d.delivery_id as delivery_id, d.delivery_date as delivery_date
LIMIT 100
            """.strip()

        return """
MATCH (n)
RETURN labels(n)[0] as entity_type, properties(n) as properties
LIMIT 25
        """.strip()
    
    def close(self):
        """Close database connection"""
        if self.executor:
            self.executor.close()


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("Few-Shot Examples:")
    print(FewShotExamples.get_few_shot_prompt())
