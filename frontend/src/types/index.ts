export enum QueryStatus {
  SUCCESS = 'success',
  REJECTED = 'rejected',
  ERROR = 'error'
}

export interface Entity {
  id: string
  type: string
  name: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  referenced_entities?: Entity[]
}

export interface GraphNode {
  id: string
  label: string
  entity_type: string
  properties: Record<string, unknown>
  relationship_count: number
}

export interface GraphEdge {
  source: string
  target: string
  relationship_type: string
  properties?: Record<string, unknown>
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  center_node_id?: string
}

export interface QueryRequest {
  query: string
  conversation_id?: string
}

export interface QueryResponse {
  status: QueryStatus
  answer: string
  referenced_entities: Entity[]
  cypher_query?: string
  execution_time_ms: number
}
