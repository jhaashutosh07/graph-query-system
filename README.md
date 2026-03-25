# Graph-Based Data Modeling & Query System

## Overview

A comprehensive system for unifying fragmented business data (orders, deliveries, invoices, payments) into a knowledge graph and enabling natural language queries through an LLM-powered interface.

**Key Features:**
- 🔗 Graph-based data model using Neo4j
- 🤖 Natural language query interface powered by Google Gemini
- 📊 Interactive graph visualization with React
- 🛡️ Multi-level guardrails to restrict domain queries
- ⚡ Fast, type-safe REST API with FastAPI
- 🐳 Docker-based deployment

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                     React Frontend                               │
│  (Graph Visualization + Chat Interface)                          │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   │ HTTP/REST
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │         Query Processing Pipeline                           ││
│  │  1. Guardrails Check (Domain Validation)                   ││
│  │  2. LLM Translation (NL → Cypher)                          ││
│  │  3. Query Execution (Graph)                                ││
│  │  4. Response Grounding (Data-backed)                       ││
│  └─────────────────────────────────────────────────────────────┘│
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   │ Cypher/Bolt
                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Neo4j Graph Database                         │
│  Entities: Order, Invoice, Delivery, Payment, Product, Customer │
│  Relationships: CONTAINS, GENERATES, SHIPS_BY, RECEIVES, etc.   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Design Principles & Guidelines

### 1. Separation of Concerns
- **Data Layer**: Neo4j (graph storage & queries)
- **Query Translation**: LLM (NL → Cypher)
- **Business Logic**: QueryEngine, Guardrails
- **Presentation**: React UI

### 2. LLM Integration Strategy
- **Few-shot prompting**: 5+ examples of NL→Cypher mappings
- **Schema context**: Detailed entity and relationship descriptions
- **Response grounding**: All answers backed by actual data
- **Fallback handling**: Template queries if LLM fails

### 3. Security & Guardrails
**Multi-level validation:**
- **Level 1**: Keyword matching (fastest)
- **Level 2**: Pattern matching (regex)
- **Level 3**: Semantic check (LLM-based)

Rejects:
- Creative writing, poetry, storytelling
- General knowledge questions
- Off-domain topics (sports, politics, etc.)
- Technical queries not related to business data

### 4. Data Model Quality
- **Unique constraints** on entity IDs
- **Indexed properties** for fast lookups
- **Typed relationships** (ALL_CAPS naming)
- **Audit metadata** (created_at, updated_at)
- **Cardinality rules** enforced

### 5. Performance Optimization
- **Query caching**: LRU in-memory + optional Redis
- **Batch operations**: Process multiple nodes/relationships
- **Lazy loading**: Fetch subgraphs on demand
- **Index-backed queries**: All frequent lookups indexed
- **Timeout protection**: 5-second query limit

---

## Project Structure

```
graph-query-system/
│
├── backend/                          # Python FastAPI backend
│   ├── app/
│   │   ├── main.py                   # FastAPI application (startup, routes)
│   │   ├── models.py                 # Pydantic schemas (type-safe requests/responses)
│   │   ├── query_engine.py           # NL→Cypher translation + execution
│   │   ├── guardrails.py             # Multi-level query validation
│   │   ├── graph_constructor.py      # Neo4j graph building
│   │   └── data_loader.py            # Dataset preprocessing
│   ├── tests/                        # Unit & integration tests
│   ├── requirements.txt              # Python dependencies
│   ├── Dockerfile                    # Backend container image
│   └── .env.example                  # Environment variables template
│
├── frontend/                         # React + TypeScript UI
│   ├── src/
│   │   ├── components/
│   │   │   ├── GraphViewer.tsx       # Force-graph visualization
│   │   │   ├── ChatPanel.tsx         # Chat interface
│   │   │   ├── MessageHistory.tsx    # Conversation display
│   │   │   └── Layout.tsx            # Main layout
│   │   ├── api/
│   │   │   └── client.ts             # API communication
│   │   ├── hooks/
│   │   │   ├── useGraph.ts           # Graph state management
│   │   │   └── useChat.ts            # Chat state management
│   │   ├── types/
│   │   │   └── index.ts              # TypeScript types
│   │   ├── contexts/
│   │   │   └── GraphContext.tsx      # Shared state context
│   │   ├── App.tsx                   # Root component
│   │   └── main.tsx                  # Entry point
│   ├── package.json                  # Dependencies
│   ├── vite.config.ts                # Vite bundler config
│   ├── Dockerfile                    # Frontend container image
│   └── .env.example                  # Environment variables template
│
├── docker-compose.yml                # Multi-container orchestration
├── DESIGN_GUIDELINES.md              # Detailed design document
├── README.md                         # This file
└── .gitignore

```

---

## Quick Start

### Prerequisites
- Docker & Docker Compose (or Python 3.11+ and Node.js 18+)
- Google Gemini API Key (free tier at https://ai.google.dev)

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone repository
git clone <your-repo>
cd graph-query-system

# 2. Set environment variables
cp .env.example .env
# Edit .env with your Gemini API key

# 3. Start all services
docker-compose up --build

# 4. Access application
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
# Neo4j Browser: http://localhost:7474

# 5. Load dataset
# See "Data Ingestion" section below
```

### Option 2: Local Development

#### Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export NEO4J_URI=bolt://localhost:7687
export GEMINI_API_KEY=<your-key>

# Run server
uvicorn app.main:app --reload
# API: http://localhost:8000
```

#### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# UI: http://localhost:3000
```

---

## Data Ingestion

### Dataset Format
Your dataset should include:
- **orders.csv** (order_id, customer_id, order_date, total_amount, status)
- **order_items.csv** (order_item_id, order_id, product_id, quantity, unit_price)
- **invoices.csv** (invoice_id, order_id, invoice_date, total_amount)
- **deliveries.csv** (delivery_id, order_id, delivery_date, destination_address)
- **payments.csv** (payment_id, invoice_id, amount, payment_date)
- **customers.csv** (customer_id, customer_name, email, country)
- **products.csv** (product_id, product_name, category, price)

### Loading Data

1. **Option A (SAP Order-to-Cash JSONL)**: place the folder `sap-order-to-cash-dataset/` at the repo root (it contains `sap-o2c-data/`).
2. **Option B (CSV sample)**: place CSVs in `./backend/data/`

2. **Load data into Neo4j (schema + nodes + relationships):**
```bash
python -m app.load_sample_data
```

`app.load_sample_data` will auto-detect the SAP dataset if `sap-order-to-cash-dataset/sap-o2c-data` exists; otherwise it falls back to the CSV sample loader.

---

## Query Examples

### Example 1: Product Analysis
**User Query:** "Which products are associated with the highest number of billing documents?"

**System Processing:**
1. ✓ Guardrails: Domain-related ✓
2. LLM generates:
   ```cypher
   MATCH (p:Product)<-[:REFERS_TO]-(oi:OrderItem)-[:IN]-(o:Order)
   MATCH (o)-[:GENERATES]->(i:Invoice)
   WITH p.product_id, p.product_name, COUNT(DISTINCT i) as invoice_count
   RETURN product_name, invoice_count
   ORDER BY invoice_count DESC LIMIT 10
   ```
3. ✓ Query executed
4. ✓ Response: "Top products by invoice count are..."

### Example 2: Flow Tracing
**User Query:** "Trace order ORD-123 through delivery to invoice and payment"

**Response:**
- Full flow visualization in graph
- Timeline view of events
- Status indicators for each stage

### Example 3: Anomaly Detection
**User Query:** "Find orders that are delivered but not yet billed"

**System Processing:**
- Patterns: Looks for Order → Delivery without Order → Invoice
- Returns incomplete flows with timeline

### Example 4: Rejected Query (Guardrails)
**User Query:** "Write a poem about shipping"

**Response:**
"This system is designed to answer questions related to the provided dataset only. Please ask about orders, deliveries, invoices, payments, customers, or products."

---

## LLM Integration

### Few-Shot Prompting Strategy

The system uses 5 carefully crafted examples to improve LLM accuracy:

```
EXAMPLE 1: Simple aggregation
  Input: "Which customers have the most orders?"
  Cypher: MATCH (c:Customer)-[:PLACES]->(o:Order)
          WITH c, COUNT(o) as order_count
          RETURN c.name, order_count
          ORDER BY order_count DESC

EXAMPLE 2: Path finding
  Input: "Trace invoice INV-001"
  Cypher: MATCH (i:Invoice {invoice_id: 'INV-001'})
          <-[:GENERATES]-(o:Order)
          RETURN entire flow...

EXAMPLE 3: Anomaly detection
  Input: "Orders without delivery"
  Cypher: MATCH (o:Order)
          WHERE NOT (o)-[:SHIPPED_BY]->(:Delivery)
          RETURN o
```

### Response Grounding

All responses are grounded in actual query results:

```python
# BAD: Hallucination
"The last order was on March 22, 2026" (if data says March 20)

# GOOD: Data-backed
"Based on the data, the most recent order is from March 20, 2026"
```

### Fallback Mechanism

If LLM fails or times out:
1. Check query cache (if exact match exists)
2. Fall back to template queries (pre-built for common intents)
3. Return error message to user

---

## Guardrails Implementation

### Level 1: Keyword Matching (Fast)
```python
# Query MUST contain domain keyword
DOMAIN_KEYWORDS = {
    "order", "delivery", "invoice", "payment", "product",
    "customer", "billing", "shipment", "amount", "status"
}
```

### Level 2: Pattern Matching
Reject patterns like:
- `creative|poetry|fiction|story`
- `general.*knowledge|how.*work`
- `politics|religion|sports`

### Level 3: Semantic Validation (Optional LLM)
```python
# Ask LLM: "Is this about business operations? YES/NO"
```

### Example Guardrail Flows

```
Query: "Write a poem about logistics"
→ Level 1: Contains keyword "logistics" ✓
→ Level 2: Matches "creative|poetry" ✗
→ Decision: REJECT

Query: "How does inventory management work?"
→ Level 1: No domain keywords ✗
→ Decision: REJECT

Query: "Which customers have unshipped orders?"
→ Level 1: Keywords "customer", "order" ✓
→ Level 2: No rejected patterns ✓
→ Decision: ACCEPT
```

---

## API Reference

### POST /api/v1/query
Process natural language query

**Request:**
```json
{
  "query": "Which products are in the most orders?",
  "conversation_id": "optional-uuid"
}
```

**Response:**
```json
{
  "status": "success",
  "answer": "The top 3 products by order count are...",
  "referenced_entities": [
    {"id": "PROD-001", "type": "Product", "name": "Laptop"}
  ],
  "cypher_query": "MATCH (p:Product)...",
  "execution_time_ms": 234.5
}
```

### GET /api/v1/info
Get system information and graph stats

**Response:**
```json
{
  "system": "Graph-Based Data Query System",
  "version": "1.0.0",
  "graph": {
    "nodes": 15000,
    "edges": 50000,
    "node_types": {"Order": 5000, "Invoice": 5000, ...}
  }
}
```

### GET /health
Health check endpoint

---

## Testing

### Unit Tests
```bash
cd backend
pytest tests/test_guardrails.py -v
pytest tests/test_query_engine.py -v
```

### Integration Tests
```bash
pytest tests/test_integration.py -v
```

### Manual Testing
```bash
# Test guardrails
python -m app.guardrails

# Test query engine
python -m app.query_engine

# Test graph construction
python -m app.graph_constructor
```

---

## Performance Considerations

### Query Optimization
- **Indexed lookups**: O(1) for entity ID searches
- **Efficient relationships**: All traversals use indexed properties
- **Result limiting**: All queries capped at 1000 rows
- **Timeout protection**: 5-second maximum query time

### Caching Strategy
```
L1: In-memory LRU cache (1ms)
  ├─ Common queries: "top products", "top customers"
  └─ Entity metadata

L2: Redis cache (10ms, optional)
  ├─ Query responses (TTL: 1 hour)
  └─ Schema information

L3: Database (50-200ms)
  └─ Full graph queries
```

### Monitoring
```bash
# Monitor query performance
curl http://localhost:8000/api/v1/info
# Returns execution stats and graph stats
```

---

## Deployment

### Docker Hub
```bash
# Build and push images
docker build -t myrepo/graph-query-backend:latest backend/
docker build -t myrepo/graph-query-frontend:latest frontend/
docker push myrepo/graph-query-backend:latest
docker push myrepo/graph-query-frontend:latest
```

### Cloud Deployment Options

#### Option 1: Render.com
```bash
# Connect GitHub repo
# Enable Auto-Deploy
# Set environment variables in dashboard
# Deploy backend and frontend as separate services
```

#### Option 2: Railway
```bash
railway link  # Connect to GitHub
railway up    # Deploy
```

#### Option 3: AWS ECS
```bash
# Create Task Definition
# Create Service with ALB
# Enable Auto Scaling
```

---

## Troubleshooting

### Backend
**Issue:** Neo4j connection failed
```bash
# Check Neo4j is running
docker ps | grep neo4j

# Verify credentials
curl -u neo4j:password123 http://localhost:7474
```

**Issue:** LLM latency/errors
```bash
# Check API key
echo $GEMINI_API_KEY

# Verify quota
# https://ai.google.dev/dashboard
```

### Frontend
**Issue:** Cannot reach backend
```bash
# Check backend is running
curl http://localhost:8000/health

# Check CORS configuration
# Edit docker-compose.yml or backend config
```

**Issue:** Graph not rendering
```bash
# Check browser console for errors
# Verify GraphQL query returns data
```

---

## Development Workflow

### Making Changes

1. **Backend Changes**
   ```bash
   cd backend
   # Make edits
   # Tests run automatically with `--reload` in Docker
   pytest tests/ -v
   ```

2. **Frontend Changes**
   ```bash
   cd frontend
   # Make edits
   # HMR (Hot Module Reload) updates automatically
   npm run dev
   ```

3. **Database Schema Changes**
   ```python
   # Edit ENTITY_SCHEMA in graph_constructor.py
   # Run initialize_schema() to create indices
   ```

### Committing Code
```bash
# Follow conventional commits
git add .
git commit -m "feat: add guardrail for creative writing"
git push origin main
```

---

## Design Decisions & Tradeoffs

### 1. Neo4j vs. DuckDB vs. SQL
**Choice: Neo4j**
- ✅ Purpose-built for graphs
- ✅ Cypher is expressive, human-readable
- ✅ Excellent relationship traversal
- ❌ Less suitable for pure analytical workloads
- ❌ Harder to scale horizontally

### 2. FastAPI vs. Flask
**Choice: FastAPI**
- ✅ Type safety with Pydantic
- ✅ Auto-generated API docs
- ✅ Built-in async support
- ✅ Better performance

### 3. React vs. Vue
**Choice: React**
- ✅ Larger ecosystem
- ✅ More graph visualization libraries
- ✅ Better TypeScript support
- ✅ Massive team/community

### 4. Google Gemini vs. GPT-4 vs. Groq
**Choice: Gemini**
- ✅ Free tier: 60 req/min
- ✅ Fast inference
- ✅ Good instruction-following
- ❌ Less mature than GPT-4

---

## Future Enhancements

### Phase 2 (Nice-to-have)
- [ ] Streaming responses (SSE)
- [ ] Conversation memory (store chat history)
- [ ] Graph clustering analysis
- [ ] Hybrid search (keyword + semantic)
- [ ] Multi-language support
- [ ] Custom user roles & permissions

### Phase 3 (Advanced)
- [ ] Temporal search (time-based filters)
- [ ] Predictive analytics (ML on graph)
- [ ] Custom user uploads
- [ ] API rate limiting per user
- [ ] Advanced graph algorithms
- [ ] Federation support

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow design guidelines in `DESIGN_GUIDELINES.md`
4. Add tests for new functionality
5. Commit with clear messages
6. Open a Pull Request

---

## License

MIT License - See LICENSE file for details

---

## Support & Questions

- **Issues**: Open a GitHub issue
- **Discussions**: Use GitHub Discussions
- **Email**: [your-email@example.com]

---

## Acknowledgments

- Design inspired by enterprise data warehousing
- Query optimization patterns from Neo4j best practices
- Guardrail design from responsible AI research
- UI patterns from modern data visualization tools

---

**Last Updated:** March 2026  
**Maintainer:** [Your Name]
