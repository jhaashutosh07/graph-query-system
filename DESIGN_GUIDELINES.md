# Graph-Based Data Modeling & Query System - Design Guidelines

## Table of Contents
1. [Core Architecture Principles](#core-architecture-principles)
2. [Design Patterns & Best Practices](#design-patterns--best-practices)
3. [Technology Stack Guidelines](#technology-stack-guidelines)
4. [Data Modeling Guidelines](#data-modeling-guidelines)
5. [LLM Integration Guidelines](#llm-integration-guidelines)
6. [Frontend Design Guidelines](#frontend-design-guidelines)
7. [Security & Guardrails](#security--guardrails)
8. [Performance Considerations](#performance-considerations)
9. [Testing & Validation](#testing--validation)

---

## Core Architecture Principles

### 1. Separation of Concerns
- **Data Layer**: Neo4j handles graph storage and queries
- **Query Translation Layer**: LLM converts NL → Cypher/SQL
- **Business Logic Layer**: Query engines, guardrails, validations
- **Presentation Layer**: React UI for graph and chat

### 2. Scalability & Extensibility
```
┌─────────────────┐
│   Frontend      │ (React, TypeScript)
├─────────────────┤
│   REST API      │ (FastAPI with Pydantic)
├─────────────────┤
│   Service Layer │ (QueryEngine, GraphConstructor)
├─────────────────┤
│   Data Layer    │ (Neo4j Driver, SQL Adapter)
└─────────────────┘
```

### 3. Data Flow
```
User Query
    ↓
[Guardrails Check] → Reject or Proceed
    ↓
[LLM Translation] → Cypher/SQL Query
    ↓
[Graph Execution] → Results
    ↓
[Response Grounding] → Data-backed NL Answer
    ↓
[Entity Extraction] → Highlight nodes in UI
```

---

## Design Patterns & Best Practices

### 1. Factory Pattern
```python
# query_engine.py
class QueryEngineFactory:
    @staticmethod
    def create_engine(backend_type: str):
        if backend_type == "neo4j":
            return Neo4jQueryEngine(...)
        elif backend_type == "sql":
            return SqlQueryEngine(...)
```

### 2. Strategy Pattern
```python
# Pluggable LLM providers
class LLMStrategy:
    def translate(query: str) -> str: ...

class GeminiStrategy(LLMStrategy): ...
class GroqStrategy(LLMStrategy): ...
```

### 3. Dependency Injection
```python
# Avoid tight coupling
def __init__(self, llm: LLMProvider, graph: GraphDB, cache: CacheStore):
    self.llm = llm
    self.graph = graph
    self.cache = cache
```

### 4. Caching Strategy
- **Query Template Cache**: Store frequent query patterns
- **Entity Cache**: Cache node metadata (products, customers)
- **Response Cache**: Response time < 1s for repeated queries

---

## Technology Stack Guidelines

### Backend Stack
| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Framework | FastAPI | ✅ Type-safe, auto-docs, async support |
| Graph DB | Neo4j | ✅ Purpose-built, Cypher language, free tier |
| LLM | Google Gemini API | ✅ 60 req/min free, low latency |
| ORM | Python Neo4j Driver | ✅ Official, well-maintained |
| Caching | Redis (optional) / In-memory | ✅ Quick development, upgrade later |
| Testing | Pytest | ✅ Standard, fixtures, mocking |

### Frontend Stack
| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Framework | React 18 | ✅ Component-based, large ecosystem |
| Language | TypeScript | ✅ Type safety, better DX |
| Build Tool | Vite | ✅ Fast bundling, HMR |
| Graph Viz | react-force-graph-3d | ✅ WebGL rendering, interactive |
| Chat UI | Custom + Shadcn/ui | ✅ Accessible, beautiful components |
| HTTP | TanStack Query + Axios | ✅ Data fetching, caching |

### Deployment
| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Containerization | Docker | ✅ Reproducible, portable |
| Orchestration | Docker Compose | ✅ Simple multi-container setup |
| Hosting | Render.com / Railway | ✅ Free tier, GitHub integration |
| Database Hosting | Neo4j Aura (free tier) | ✅ Managed, secure |

---

## Data Modeling Guidelines

### 1. Entity Definition
Each entity must have:
```python
class Entity:
    id: str                    # Unique identifier (UUID)
    entity_type: str          # "Order", "Product", etc.
    properties: Dict[str, Any] # name, amount, created_at, etc.
    metadata: Dict[str, str]  # audit trail, source, version
```

### 2. Node Properties (Neo4j)
```cypher
(:Order {
    order_id: "ORD-001",
    customer_id: "CUST-123",
    order_date: "2024-01-15",
    total_amount: 1500.00,
    status: "completed",
    created_at: "2024-01-15T10:30:00Z",
    updated_at: "2024-01-20T14:22:00Z"
})
```

### 3. Relationship Types
```
Clear naming convention: PAST_TENSE or ALL_CAPS
✅ CONTAINS, SHIPS_TO, INVOICES, MAKES_PAYMENT
❌ has, order-delivery, customer_order
```

### 4. Graph Cardinality Rules
- 1-to-many: One customer → many orders
- Many-to-many: Products ↔ Orders (through OrderItems)
- Avoid circular relationships without intermediate nodes

### 5. Data Constraints
```
:Order
  - order_id: UNIQUE, NOT NULL
  - customer_id: Required, indexed
  - order_date: Required, <= NOW()

:Product
  - product_id: UNIQUE, NOT NULL
  - price: >= 0, numeric

:Payment
  - payment_id: UNIQUE, NOT NULL
  - amount: > 0, matches invoice total
```

### 6. Indexing Strategy
```cypher
-- Primary Keys
CREATE CONSTRAINT order_id_unique ON (o:Order) ASSERT o.order_id IS UNIQUE;

-- Lookup Indices
CREATE INDEX order_date ON :Order(order_date);
CREATE INDEX customer_id ON :Order(customer_id);
CREATE INDEX product_category ON :Product(category);
```

---

## LLM Integration Guidelines

### 1. Few-Shot Prompt Engineering
```
STRUCTURE:
[System Role] → [Domain Context] → [Examples] → [User Query] → [Output Format]

EXAMPLE:
System: "You are a business analyst. Answer only based on provided data."
Context: "Database contains Orders, Deliveries, Invoices, Payments. 
          Relationships: Order → Delivery → Invoice → Payment"
Examples:
  Q: "Which products are in top 5 orders?"
  A: "MATCH (p:Product)<-[:ORDERED]-(oi:OrderItem)-[:IN]-(o:Order) 
     WITH p, COUNT(o) as cnt RETURN p.name, cnt ORDER BY cnt DESC LIMIT 5"

User Query: "Which products are in the most orders?"
Output Format: "Return ONLY the Cypher query without explanation"
```

### 2. Chain-of-Thought for Complex Queries
```
For multi-step queries, ask LLM to:
1. Identify entities (Order, Invoice, Product)
2. Identify relationships (connections)
3. Build query step-by-step
4. Validate against schema
```

### 3. Response Grounding Rules
```python
# CRITICAL: All answers must be grounded in data
def ground_response(user_query, results, llm):
    """
    1. Get results from database
    2. Pass ONLY results to LLM for interpretation
    3. LLM must cite data in response
    4. Reject hallucinations
    """
    if not results:
        return "No data found for this query."
    
    response = llm.generate_response(
        user_query=user_query,
        results=results,
        constraint="You MUST use only the provided data. Do not generate information."
    )
    return response
```

### 4. Prompt Caching
```python
# Cache system prompts + schema to reduce API latency
SYSTEM_PROMPT_HASH = hash(SYSTEM_PROMPT + SCHEMA)
if SYSTEM_PROMPT_HASH in cache:
    llm_config = cache[SYSTEM_PROMPT_HASH]
else:
    llm_config = llm.set_system_prompt(...)
```

### 5. Error Handling in LLM
```python
# Gracefully handle LLM failures
try:
    query = llm.translate_to_cypher(user_input)
except LLMError as e:
    # Fallback to template queries
    query = TEMPLATE_QUERIES.get(Intent.from_text(user_input))
```

---

## Frontend Design Guidelines

### 1. Component Hierarchy
```
App
├── Header
├── Main Layout
│   ├── GraphViewer (60% width)
│   │   ├── Canvas (force-graph)
│   │   ├── Controls (zoom, reset, expand)
│   │   └── NodeDetail (metadata panel)
│   └── ChatPanel (40% width)
│       ├── MessageHistory
│       ├── MessageInput
│       └── LoadingIndicator
└── Footer (status bar)
```

### 2. State Management
```typescript
// Use React Context for shared state
interface GraphState {
  nodes: Node[];
  edges: Edge[];
  selectedNode: Node | null;
  highlightedNodes: Set<string>;
  loading: boolean;
  error: string | null;
}

interface ChatState {
  messages: Message[];
  isWaiting: boolean;
  conversationId: string;
}
```

### 3. Data Fetching Pattern
```typescript
// Use TanStack Query for efficient data management
const { data: graphData, isLoading, error } = useQuery({
  queryKey: ['graph', nodeId],
  queryFn: () => fetchSubgraph(nodeId),
  staleTime: 5 * 60 * 1000, // 5 min cache
  gcTime: 10 * 60 * 1000
});
```

### 4. UI/UX Principles
- **Progressive Disclosure**: Show summary first, expand on demand
- **Real-time Feedback**: Loading states, success/error messages
- **Accessibility**: ARIA labels, keyboard navigation, high contrast
- **Mobile Responsive**: (Secondary priority, but support landscape mode)
- **Dark Mode**: Optional but appreciated (uses CSS variables)

### 5. Performance Optimization
```typescript
// Memoize expensive components
const GraphViewer = React.memo(({ nodes, edges }) => {
  return <ForceGraph3D data={{ nodes, edges }} />;
});

// Debounce rapid queries
const debouncedSearch = useMemo(
  () => debounce((query: string) => queryGraph(query), 300),
  []
);
```

### 6. Error Boundaries
```typescript
<ErrorBoundary fallback={<ErrorUI />}>
  <GraphViewer />
  <ChatPanel />
</ErrorBoundary>
```

---

## Security & Guardrails

### 1. Input Validation
```python
from pydantic import BaseModel, validator

class QueryRequest(BaseModel):
    query: str
    
    @validator('query')
    def query_length(cls, v):
        if len(v) > 500:
            raise ValueError("Query too long")
        return v
```

### 2. Guard Rail Categories
```
Level 1: Keyword Filter (Fast)
  ❌ Reject if: NOT (order|delivery|invoice|payment|product|customer|billing)
  
Level 2: Pattern Matching (Fast)
  ❌ Reject if matches: creative writing, jokes, general knowledge
  
Level 3: Semantic Check (LLM-based, slower)
  ❌ Ask LLM: "Is this query about business operations? YES/NO"
  
Level 4: Result Validation
  ❌ Reject empty results with generic message
  ❌ Cap result size to 1000 rows
```

### 3. Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/query")
@limiter.limit("30/minute")
async def query_endpoint(request: QueryRequest):
    pass
```

### 4. Query Injection Prevention
```python
# ✅ GOOD: Parameterized Cypher using Neo4j driver
tx.run("MATCH (o:Order) WHERE o.order_id = $id RETURN o", id=user_input)

# ❌ BAD: String concatenation
tx.run(f"MATCH (o:Order) WHERE o.order_id = '{user_input}' RETURN o")
```

### 5. Privacy & Data Protection
- No logging of sensitive data (amounts, customer info)
- No storage of failed queries (potential attack vectors)
- Rate limit by IP to prevent abuse
- Sanitize error messages (no stack traces in responses)

---

## Performance Considerations

### 1. Query Optimization
```cypher
-- ✅ Good: Uses indices
MATCH (p:Product {category: "Electronics"})
RETURN p

-- ❌ Bad: Full table scan
MATCH (p:Product)
WHERE p.category = "Electronics"
RETURN p
```

### 2. Graph Query Limits
```python
# Prevent expensive queries
MAX_RESULTS = 1000
MAX_DEPTH = 4  # Don't traverse beyond 4 hops
QUERY_TIMEOUT = 5000  # milliseconds
```

### 3. Lazy Loading Strategy
```typescript
// Don't load entire graph initially
// Fetch subgraphs on demand when user clicks nodes

const handleExpandNode = async (nodeId: string) => {
  const neighbors = await fetchNeighbors(nodeId, depth=2);
  updateGraph(addNodes(neighbors));
};
```

### 4. Caching Layers
```
User Request
  ↓
[L1: In-memory LRU Cache] (1ms) - responses
  ↓
[L2: Redis Cache] (10ms) - common queries
  ↓
[L3: Database] (50-200ms) - graph queries
```

### 5. Batch Operations
```python
# Batch multiple queries instead of individual requests
@app.post("/api/queries/batch")
async def batch_queries(queries: List[QueryRequest]):
    results = [process_query(q) for q in queries]
    return results
```

---

## Testing & Validation

### 1. Unit Tests
```python
# test_guardrails.py
def test_reject_out_of_domain():
    assert guardrails.is_domain_query("write a poem") == False
    assert guardrails.is_domain_query("list all orders") == True
```

### 2. Integration Tests
```python
# test_query_engine.py
def test_end_to_end_query():
    result = query_engine.process("Top 5 products by revenue?")
    assert result['answer'] is not None
    assert result['status'] == 'success'
```

### 3. Graph Validation
```python
def validate_graph():
    # Check for orphaned nodes (no relationships)
    orphaned = graph.run("MATCH (n) WHERE NOT (n)--() RETURN COUNT(n)")
    assert orphaned == 0, "Found orphaned nodes"
    
    # Verify referential integrity
    broken_refs = graph.run("""
        MATCH (o:Order)-[:CONTAINS]->(i)
        WHERE NOT EXISTS((i:OrderItem))
        RETURN COUNT(*)
    """)
    assert broken_refs == 0
```

### 4. LLM Output Validation
```python
def validate_llm_output(query: str, response: str):
    # 1. Check response is grounded (contains data)
    if len(response) < 20:
        return False, "Response too short"
    
    # 2. Check response answers the original query
    relevance = semantic_similarity(query, response)
    if relevance < 0.6:
        return False, "Response off-topic"
    
    return True, response
```

### 5. Test Data
```sql
-- Create small test dataset
CREATE (:Customer {customer_id: "TEST-1", name: "Test Customer"})
CREATE (:Order {order_id: "TEST-ORD-1", customer_id: "TEST-1"})
...
```

---

## Naming Conventions

### Database
```
Node types:    PascalCase (Order, Customer, Product)
Properties:    snake_case (order_date, customer_id, total_amount)
Relationships: ALL_CAPS (CONTAINS, SHIPS_TO, INVOICES)
Indices:       entity_property (order_order_date, product_category)
```

### Code
```python
# Functions
def translate_query_to_cypher(query: str) -> str: ...

# Classes
class QueryEngine: ...

# Constants
MAX_QUERY_DEPTH = 4
DOMAIN_KEYWORDS = {"order", "delivery", ...}
```

### Files
```
/backend
  ├── app.py (main FastAPI app)
  ├── query_engine.py (translation logic)
  ├── graph_constructor.py (data → Neo4j)
  ├── guardrails.py (validation)
  └── models.py (Pydantic schemas)

/frontend
  ├── src/components/
  │   ├── GraphViewer.tsx
  │   ├── ChatPanel.tsx
  │   └── MessageHistory.tsx
```

---

## Summary Table

| Aspect | Guideline |
|--------|-----------|
| Code Quality | Type hints, docstrings, 80%+ test coverage |
| Performance | Query timeout 5s, cache common queries, lazy load UI |
| Security | Parameterized queries, rate limiting, input validation |
| User Experience | Progressive disclosure, real-time feedback, error handling |
| Data Integrity | Constraints, indices, referential integrity checks |
| LLM Quality | Few-shot examples, data grounding, response validation |
| Documentation | Schema diagrams, prompt examples, API docs (auto-generated) |

