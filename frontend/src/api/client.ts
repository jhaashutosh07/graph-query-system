import axios from 'axios'
import type { GraphData, QueryRequest, QueryResponse } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

const http = axios.create({
  baseURL: API_BASE
})

export async function queryGraph(payload: QueryRequest): Promise<QueryResponse> {
  const response = await http.post<QueryResponse>('/api/v1/query', payload)
  return response.data
}

export async function getGraphOverview(limit = 80): Promise<GraphData> {
  const response = await http.get<GraphData>('/api/v1/graph/overview', {
    params: { limit }
  })
  return response.data
}

export async function getSubgraph(entityId: string, depth = 2): Promise<GraphData> {
  const response = await http.get<GraphData>(`/api/v1/graph/subgraph/${encodeURIComponent(entityId)}`, {
    params: { depth }
  })
  return response.data
}

export async function getNodeMetadata(nodeId: string): Promise<any> {
  const response = await http.get<any>(`/api/v1/graph/node/${encodeURIComponent(nodeId)}`)
  return response.data
}
