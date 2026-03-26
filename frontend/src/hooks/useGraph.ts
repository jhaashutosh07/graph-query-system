import { useCallback, useEffect, useState } from 'react'
import { getGraphOverview, getSubgraph } from '../api/client'
import type { GraphData, GraphNode } from '../types'

export function useGraph() {
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] })
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadOverview = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getGraphOverview(80)
      setGraph(data)
    } catch {
      setError('Failed to load graph overview')
    } finally {
      setLoading(false)
    }
  }, [])

  const focusNode = useCallback(async (node: GraphNode) => {
    setSelectedNode(node)
    setLoading(true)
    setError(null)
    try {
      const data = await getSubgraph(node.id, 2)
      setGraph(data)
    } catch {
      setError(`Failed to load subgraph for ${node.id}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  return {
    graph,
    selectedNode,
    loading,
    error,
    loadOverview,
    focusNode
  }
}
