import ForceGraph2D from 'react-force-graph-2d'
import { useMemo } from 'react'
import { useGraphContext } from '../contexts/GraphContext'
import type { GraphNode } from '../types'
import { getNodeMetadata } from '../api/client'
import { useEffect, useState } from 'react'

export function GraphViewer() {
  const { graph, loading, error, selectedNode, focusNode, loadOverview } = useGraphContext()
  const { nodeMetadata, nodeMetadataLoading } = useNodeMetadata(selectedNode)

  const data = useMemo(() => ({
    nodes: graph.nodes.map((node) => ({ ...node })),
    links: graph.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      label: edge.relationship_type
    }))
  }), [graph])

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Knowledge Graph</h2>
        <button onClick={() => void loadOverview()} disabled={loading}>Reset View</button>
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="graph-wrap">
        <ForceGraph2D
          graphData={data}
          nodeLabel={(node) => `${(node as GraphNode).entity_type}: ${(node as GraphNode).label}`}
          linkLabel={(link) => String(link.label || '')}
          nodeAutoColorBy="entity_type"
          nodeCanvasObject={(node, ctx, globalScale) => {
            const graphNode = node as GraphNode
            const label = graphNode.label || graphNode.id
            const fontSize = 12 / globalScale
            ctx.font = `${fontSize}px Sans-Serif`
            ctx.fillStyle = selectedNode?.id === graphNode.id ? '#111827' : '#1f2937'
            ctx.fillText(label, (graphNode.x || 0) + 6, (graphNode.y || 0) + 4)
          }}
          onNodeClick={(node) => void focusNode(node as GraphNode)}
        />
      </div>
      <p className="meta-text">
        Nodes: {graph.nodes.length} | Edges: {graph.edges.length}
      </p>

      {selectedNode && (
        <div className="metadata-panel">
          <h3>Node Metadata</h3>
          <p className="meta-text">
            {selectedNode.entity_type} • {selectedNode.id}
          </p>
          {nodeMetadataLoading && <p className="meta-text">Loading metadata...</p>}
          {nodeMetadata && (
            <pre className="metadata-pre">{JSON.stringify(nodeMetadata, null, 2)}</pre>
          )}
        </div>
      )}
    </section>
  )
}

// Fetch metadata for selected nodes.
function useNodeMetadata(selectedNode: GraphNode | null) {
  const [nodeMetadata, setNodeMetadata] = useState<any>(null)
  const [nodeMetadataLoading, setNodeMetadataLoading] = useState(false)

  useEffect(() => {
    if (!selectedNode) {
      setNodeMetadata(null)
      return
    }

    setNodeMetadataLoading(true)
    void getNodeMetadata(selectedNode.id)
      .then((res) => setNodeMetadata(res))
      .catch(() => setNodeMetadata(null))
      .finally(() => setNodeMetadataLoading(false))
  }, [selectedNode])

  return { nodeMetadata, nodeMetadataLoading }
}
