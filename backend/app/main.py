"""
FastAPI Main Application: REST API for graph query system.

Design Pattern:
1. Dependency injection for services
2. Structured error handling
3. API versioning (/api/v1/)
4. Type-safe endpoints with Pydantic
5. Rate limiting
6. Async/await for performance

Following DESIGN_GUIDELINES.md API design principles
"""

import os
import logging
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.models import (
    QueryRequest, QueryResponse, ErrorResponse, QueryStatus,
    SubgraphRequest, NodeMetadataRequest, Neo4jConfig, LLMConfig
)
from app.guardrails import Guardrails, QueryCategory
from app.graph_constructor import GraphConstructor
from app.query_engine import QueryEngine
from app.llm_client import LLMClient

# ============================================================================
# Configuration & Setup
# ============================================================================

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AUTO_LOAD_SAMPLE_DATA = os.getenv("AUTO_LOAD_SAMPLE_DATA", "false").lower() in {"1", "true", "yes", "y"}

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Global service instances
llm_client: Optional[LLMClient] = None
query_engine = None
guardrails = None
graph_constructor = None


# ============================================================================
# Application Lifecycle
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown"""
    
    # Startup
    logger.info("Starting Graph Query System...")
    
    try:
        # Initialize LLM
        global llm_client
        if GEMINI_API_KEY:
            llm_client = LLMClient(api_key=GEMINI_API_KEY)
            logger.info("✓ Gemini LLM initialized")
        else:
            logger.warning("⚠ GEMINI_API_KEY not set - LLM features disabled")
        
        # Initialize Guardrails
        global guardrails
        guardrails = Guardrails(llm_provider=llm_client)
        logger.info("✓ Guardrails initialized")
        
        # Initialize Graph Constructor & Query Engine
        global graph_constructor, query_engine
        graph_constructor = GraphConstructor(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        logger.info("✓ Neo4j connection established")
        
        # Initialize schema (idempotent)
        schema_stats = graph_constructor.initialize_schema()
        logger.info(f"✓ Schema initialized: {schema_stats.constraints_created} constraints, "
                   f"{schema_stats.indices_created} indices")

        # Optionally seed graph from CSVs (for demos / CI)
        if AUTO_LOAD_SAMPLE_DATA:
            try:
                summary = graph_constructor.get_graph_summary()
                if summary.get("total_nodes", 0) == 0:
                    from app.load_sample_data import main as load_sample_main
                    logger.info("Seeding Neo4j with sample dataset...")
                    load_sample_main()
                    logger.info("✓ Sample dataset loaded")
            except Exception as e:
                logger.warning(f"Sample data auto-load skipped: {e}")
        
        # Initialize Query Engine
        query_engine = QueryEngine(
            llm_provider=llm_client,
            neo4j_uri=NEO4J_URI,
            neo4j_user=NEO4J_USER,
            neo4j_password=NEO4J_PASSWORD,
            guardrails=guardrails
        )
        logger.info("✓ Query engine initialized")
        
        logger.info("Application startup complete!")
    
    except Exception as e:
        logger.error(f"Startup failed: {e}", exc_info=True)
        raise
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down Graph Query System...")
    try:
        if query_engine:
            query_engine.close()
        if graph_constructor:
            graph_constructor.close()
        logger.info("✓ Graceful shutdown complete")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")


# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="Graph-Based Query System",
    description="Natural language interface for business data",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting
app.state.limiter = limiter


# ============================================================================
# Health Check & Info Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "neo4j": "connected",
                "llm": "gemini" if (llm_client and llm_client.is_enabled) else "disabled"
        }
    }


@app.get("/api/v1/info")
async def get_info():
    """Get system info and schema"""
    try:
        if not graph_constructor:
            raise HTTPException(status_code=500, detail="Graph not initialized")
        
        summary = graph_constructor.get_graph_summary()
        validation = graph_constructor.validate_graph_integrity()
        
        return {
            "system": "Graph-Based Data Query System",
            "version": "1.0.0",
            "graph": {
                "nodes": summary["total_nodes"],
                "edges": summary["total_edges"],
                "node_types": summary["node_types"]
            },
            "validation": validation
        }
    except Exception as e:
        logger.error(f"Info endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Main Query Endpoint
# ============================================================================

@app.post(
    "/api/v1/query",
    response_model=QueryResponse,
    summary="Process natural language query",
    tags=["Query"]
)
@limiter.limit("30/minute")
async def process_query(payload: QueryRequest, request: Request):
    """
    Process a natural language query against the knowledge graph.
    
    Request body:
    ```json
    {
        "query": "Which products are in the most orders?"
    }
    ```
    
    Response:
    ```json
    {
        "status": "success",
        "answer": "The top 3 products are...",
        "referenced_entities": [...],
        "cypher_query": "MATCH ..."
    }
    ```
    """
    try:
        if not query_engine:
            raise HTTPException(
                status_code=503,
                detail="Query engine not initialized"
            )
        
        logger.info(f"Processing query: {payload.query}")
        
        # Process query through engine
        result = query_engine.process_query(payload.query)
        
        # Map result to response model
        response = QueryResponse(
            status=QueryStatus(result["status"]),
            answer=result["answer"],
            referenced_entities=result["referenced_entities"],
            cypher_query=result.get("cypher_query"),
            execution_time_ms=result["execution_time_ms"]
        )
        
        logger.info(f"Query processed successfully: {response.status.value}")
        return response
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# Graph Navigation Endpoints
# ============================================================================

@app.get(
    "/api/v1/graph/subgraph/{entity_id}",
    summary="Get subgraph around entity",
    tags=["Graph"]
)
@limiter.limit("60/minute")
async def get_subgraph(
    request: Request,
    entity_id: str,
    depth: int = 2,
):
    """
    Get subgraph around a specific entity.
    
    Args:
        entity_id: Node ID
        depth: Relationship depth (1-4)
    
    Returns:
        Graph data with nodes and edges
    """
    if depth < 1 or depth > 4:
        raise HTTPException(status_code=400, detail="Depth must be between 1 and 4")
    
    try:
        if not query_engine:
            raise HTTPException(status_code=503, detail="Query engine not initialized")
        
        center_lookup = """
        MATCH (n)
        WHERE any(k IN keys(n) WHERE k ENDS WITH '_id' AND toString(n[k]) = $entity_id)
        RETURN elementId(n) as center_eid, labels(n)[0] as center_label, properties(n) as center_props
        LIMIT 1
        """
        center_rows = query_engine.executor.execute_cypher(center_lookup, {"entity_id": entity_id})
        if not center_rows:
            raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

        center_eid = center_rows[0]["center_eid"]

        node_query = f"""
        MATCH (center) WHERE elementId(center) = $center_eid
        OPTIONAL MATCH p=(center)-[*0..{depth}]-(n)
        UNWIND CASE WHEN p IS NULL THEN [center] ELSE nodes(p) END as node
        RETURN DISTINCT elementId(node) as eid, labels(node)[0] as node_type, properties(node) as props
        LIMIT 1000
        """
        edge_query = f"""
        MATCH (center) WHERE elementId(center) = $center_eid
        OPTIONAL MATCH p=(center)-[*1..{depth}]-(n)
        UNWIND CASE WHEN p IS NULL THEN [] ELSE relationships(p) END as rel
        RETURN DISTINCT
            elementId(startNode(rel)) as source_eid,
            elementId(endNode(rel)) as target_eid,
            type(rel) as rel_type,
            properties(rel) as rel_props
        LIMIT 2000
        """
        node_rows = query_engine.executor.execute_cypher(node_query, {"center_eid": center_eid})
        edge_rows = query_engine.executor.execute_cypher(edge_query, {"center_eid": center_eid})

        formatted = _format_graph_payload(node_rows, edge_rows)
        return {
            "nodes": formatted["nodes"],
            "edges": formatted["edges"],
            "center_node_id": entity_id
        }
    
    except Exception as e:
        logger.error(f"Subgraph error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/graph/overview",
    summary="Get lightweight graph overview",
    tags=["Graph"]
)
@limiter.limit("60/minute")
async def get_graph_overview(request: Request, limit: int = 80):
    if limit < 10 or limit > 300:
        raise HTTPException(status_code=400, detail="Limit must be between 10 and 300")

    try:
        if not query_engine:
            raise HTTPException(status_code=503, detail="Query engine not initialized")

        nodes_query = """
        MATCH (n)
        RETURN elementId(n) as eid, labels(n)[0] as node_type, properties(n) as props
        LIMIT $limit
        """
        node_rows = query_engine.executor.execute_cypher(nodes_query, {"limit": limit})
        eid_list = [row["eid"] for row in node_rows]

        edge_query = """
        MATCH (a)-[r]->(b)
        WHERE elementId(a) IN $ids AND elementId(b) IN $ids
        RETURN DISTINCT
            elementId(a) as source_eid,
            elementId(b) as target_eid,
            type(r) as rel_type,
            properties(r) as rel_props
        LIMIT 1000
        """
        edge_rows = query_engine.executor.execute_cypher(edge_query, {"ids": eid_list})
        return _format_graph_payload(node_rows, edge_rows)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Graph overview error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/v1/graph/node/{node_id}",
    summary="Get node metadata",
    tags=["Graph"]
)
@limiter.limit("100/minute")
async def get_node_metadata(node_id: str, request: Request):
    """
    Get detailed metadata for a specific node.
    """
    try:
        if not query_engine:
            raise HTTPException(status_code=503, detail="Query engine not initialized")
        
        cypher = """
        MATCH (n)
        WHERE any(k IN keys(n) WHERE k ENDS WITH '_id' AND toString(n[k]) = $node_id)
        RETURN n, labels(n) as types
        LIMIT 1
        """
        
        results = query_engine.executor.execute_cypher(cypher, {"node_id": node_id})
        
        if not results:
            raise HTTPException(status_code=404, detail="Node not found")

        raw = results[0]
        neo_node = raw.get("n")
        labels = raw.get("types") or []

        props = dict(neo_node) if neo_node is not None else {}
        entity_type = labels[0] if labels else None

        return {
            "id": node_id,
            "entity_type": entity_type,
            "labels": labels,
            "properties": props
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Node metadata error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _pick_node_id(eid: str, props: Dict[str, Any]) -> str:
    for key, value in props.items():
        if key.endswith("_id") and value is not None:
            return str(value)
    return eid


def _format_graph_payload(node_rows: List[Dict[str, Any]], edge_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_eid: Dict[str, Dict[str, Any]] = {}
    for row in node_rows:
        eid = row["eid"]
        props = row.get("props", {}) or {}
        node_id = _pick_node_id(eid, props)
        label = props.get("name") or props.get("customer_name") or props.get("product_name") or node_id
        by_eid[eid] = {
            "id": node_id,
            "label": str(label),
            "entity_type": row.get("node_type", "Unknown"),
            "properties": props,
            "relationship_count": 0
        }

    edges = []
    for row in edge_rows:
        source = by_eid.get(row["source_eid"])
        target = by_eid.get(row["target_eid"])
        if not source or not target:
            continue

        source["relationship_count"] += 1
        target["relationship_count"] += 1
        edges.append({
            "source": source["id"],
            "target": target["id"],
            "relationship_type": row.get("rel_type", "RELATED_TO"),
            "properties": row.get("rel_props", {})
        })

    return {"nodes": list(by_eid.values()), "edges": edges}


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API documentation link"""
    return {
        "message": "Graph-Based Query System",
        "documentation": "/docs",
        "api_base": "/api/v1/",
        "endpoints": {
            "health": "GET /health",
            "info": "GET /api/v1/info",
            "query": "POST /api/v1/query",
            "subgraph": "GET /api/v1/graph/subgraph/{entity_id}",
            "node": "GET /api/v1/graph/node/{node_id}"
        }
    }


# ============================================================================
# Development Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
