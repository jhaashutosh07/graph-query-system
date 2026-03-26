"""
Pydantic models for API requests, responses, and internal data structures.

Following the design guidelines:
- Input validation with constraints
- Clear type hints
- Docstrings for complex fields
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Set
from datetime import datetime
from enum import Enum


class QueryStatus(str, Enum):
    """Query processing status"""
    SUCCESS = "success"
    REJECTED = "rejected"
    ERROR = "error"


# ============================================================================
# API Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """User query request for graph interaction
    
    Constraints:
    - query length: 10-500 characters
    - prevents injection attacks
    """
    query: str = Field(..., min_length=10, max_length=500)
    conversation_id: Optional[str] = None
    
    @validator('query')
    def query_not_empty(cls, v):
        """Ensure query is not just whitespace"""
        if not v.strip():
            raise ValueError("Query cannot be empty or whitespace")
        return v.strip()


class GraphNode(BaseModel):
    """Represents a node in the knowledge graph"""
    id: str  # UUID or entity ID
    label: str  # Display name
    entity_type: str  # Order, Product, Customer, etc.
    properties: Dict[str, Any]  # Node attributes
    relationship_count: int = 0


class GraphEdge(BaseModel):
    """Represents a relationship between nodes"""
    source: str
    target: str
    relationship_type: str  # CONTAINS, SHIPS_TO, etc.
    properties: Optional[Dict[str, Any]] = None


class GraphData(BaseModel):
    """Complete graph snapshot for visualization"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    center_node_id: Optional[str] = None


class QueryResponse(BaseModel):
    """Response containing answer and graph context"""
    status: QueryStatus
    answer: str  # Natural language answer
    referenced_entities: List[Dict[str, Any]]  # Entities used in answer
    cypher_query: Optional[str] = None  # Debug: show generated query
    execution_time_ms: float  # Performance metric
    
    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "answer": "The top product is 'Laptop' with 5 orders.",
                "referenced_entities": [
                    {"id": "PROD-001", "type": "Product", "name": "Laptop"}
                ],
                "execution_time_ms": 234.5
            }
        }


class ErrorResponse(BaseModel):
    """Error response format"""
    status: QueryStatus = QueryStatus.ERROR
    message: str
    error_code: Optional[str] = None


class NodeMetadataRequest(BaseModel):
    """Request for detailed node information"""
    node_id: str


class SubgraphRequest(BaseModel):
    """Request for subgraph around a node"""
    center_node_id: str
    depth: int = Field(default=2, ge=1, le=4)  # Max depth guideline


# ============================================================================
# Internal Models
# ============================================================================

class Entity(BaseModel):
    """Internal representation of a graph entity"""
    entity_id: str
    entity_type: str  # Must be one of known types
    properties: Dict[str, Any]
    metadata: Dict[str, str]  # audit info
    created_at: datetime
    updated_at: datetime


class QueryIntent(BaseModel):
    """Extracted intent from user query"""
    intent_type: str  # "list", "count", "trace", "find_broken"
    entities: Set[str]  # Entities mentioned
    relationships: Set[str]  # Relationships mentioned
    is_domain_query: bool
    confidence: float = Field(ge=0.0, le=1.0)


class LLMPromptContext(BaseModel):
    """Context for LLM prompt generation"""
    schema_description: str  # Entity and relationship descriptions
    examples: List[Dict[str, str]]  # Few-shot examples
    user_query: str
    domain_keywords: Set[str]
    system_role: str = "You are a business intelligence analyst"


class CypherQuery(BaseModel):
    """Generated Cypher query with metadata"""
    query: str
    estimated_complexity: str  # "simple", "moderate", "complex"
    expected_result_type: str  # "nodes", "relationships", "path", etc.


# ============================================================================
# Chat & Conversation Models
# ============================================================================

class Message(BaseModel):
    """Single message in conversation"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    referenced_entities: Optional[List[str]] = None


class ConversationContext(BaseModel):
    """Maintains conversation state"""
    conversation_id: str
    messages: List[Message]
    highlighted_nodes: Set[str] = Field(default_factory=set)
    last_query_cypher: Optional[str] = None


# ============================================================================
# Validation & Guardrail Models
# ============================================================================

class GuardrailCheckResult(BaseModel):
    """Result of guardrail validation"""
    is_valid: bool
    reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    severity: str = "info"  # "info", "warning", "error"


class DomainKeywords(BaseModel):
    """Domain-specific keywords for validation"""
    entities: Set[str]
    operations: Set[str]
    out_of_domain_patterns: Set[str]


# ============================================================================
# Configuration Models
# ============================================================================

class Neo4jConfig(BaseModel):
    """Neo4j connection configuration"""
    uri: str = Field("bolt://localhost:7687")
    username: str = Field("neo4j")
    password: str = Field(...)
    database: str = Field("neo4j")
    echo: bool = False


class LLMConfig(BaseModel):
    """LLM provider configuration"""
    provider: str = "gemini"  # gemini, groq, openrouter
    api_key: str
    model: str = "gemini-pro"
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = 1000


class AppConfig(BaseModel):
    """Application configuration"""
    neo4j: Neo4jConfig
    llm: LLMConfig
    debug_mode: bool = False
    rate_limit_per_minute: int = 30
    query_timeout_seconds: int = 5
    max_result_rows: int = 1000
