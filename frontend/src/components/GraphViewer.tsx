import ForceGraph2D from 'react-force-graph-2d'
import { useMemo, useState, useRef } from 'react'
import { useGraphContext } from '../contexts/GraphContext'
import type { GraphNode } from '../types'
import { getNodeMetadata } from '../api/client'
import { useEffect } from 'react'

export function GraphViewer() {
  const { graph, loading, error, selectedNode, focusNode, loadOverview } = useGraphContext()
  const { nodeMetadata, nodeMetadataLoading } = useNodeMetadata(selectedNode)
  const [showOverlay, setShowOverlay] = useState(true)
  const [zoomLevel, setZoomLevel] = useState(100)
  const graphRef = useRef<any>()

  const data = useMemo(() => ({
    nodes: graph.nodes.map((node) => ({ ...node })),
    links: graph.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
      label: edge.relationship_type
    }))
  }), [graph])

  const handleZoomIn = () => {
    if (graphRef.current) {
      graphRef.current.zoom(graphRef.current.zoom() * 1.2)
    }
  }

  const handleZoomOut = () => {
    if (graphRef.current) {
      graphRef.current.zoom(graphRef.current.zoom() / 1.2)
    }
  }

  const handleResetView = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400)
    }
  }

  const handleMinimize = () => {
    focusNode(null)
  }

  return (
    <section className="graph-container">
      <div className="graph-controls">
        <button className="control-btn" onClick={handleMinimize} data-testid="minimize-btn">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h4a1 1 0 010 2H6.414l2.293 2.293a1 1 0 01-1.414 1.414L5 6.414V8a1 1 0 01-2 0V4zm9 1a1 1 0 010-2h4a1 1 0 011 1v4a1 1 0 01-2 0V6.414l-2.293 2.293a1 1 0 11-1.414-1.414L13.586 5H12zm-9 7a1 1 0 012 0v1.586l2.293-2.293a1 1 0 011.414 1.414L6.414 15H8a1 1 0 010 2H4a1 1 0 01-1-1v-4zm13-1a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 010-2h1.586l-2.293-2.293a1 1 0 011.414-1.414L15 13.586V12a1 1 0 011-1z" clipRule="evenodd" />
          </svg>
          Minimize
        </button>
        <button 
          className="control-btn" 
          onClick={() => setShowOverlay(!showOverlay)}
          data-testid="hide-overlay-btn"
        >
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
            <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
          </svg>
          Hide Granular Overlay
        </button>
      </div>

      {error && <p className="error-text">{error}</p>}
      
      <div className="graph-wrap">
        <ForceGraph2D
          ref={graphRef}
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
          onZoom={(transform) => {
            setZoomLevel(Math.round(transform.k * 100))
          }}
        />
      </div>

      <div className="zoom-controls">
        <button className="zoom-btn" onClick={() => void loadOverview()} title="Back" data-testid="zoom-back-btn">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clipRule="evenodd" />
          </svg>
        </button>
        <button className="zoom-btn" title="Forward" data-testid="zoom-forward-btn">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
        <button className="zoom-btn" onClick={handleZoomOut} title="Zoom out" data-testid="zoom-out-btn">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
        </button>
        <div className="zoom-display" data-testid="zoom-level">{zoomLevel}%</div>
        <button className="zoom-btn" onClick={handleZoomIn} title="Zoom in" data-testid="zoom-in-btn">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
          </svg>
        </button>
        <button className="zoom-btn" onClick={handleResetView} title="Reset view" data-testid="zoom-reset-btn">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
          </svg>
        </button>
        <button className="zoom-btn" title="Pan mode" data-testid="pan-mode-btn">
          <svg viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M9 3a1 1 0 012 0v5.5a.5.5 0 001 0V4a1 1 0 112 0v4.5a.5.5 0 001 0V6a1 1 0 112 0v5a7 7 0 11-14 0V9a1 1 0 012 0v2.5a.5.5 0 001 0V4a1 1 0 012 0v4.5a.5.5 0 001 0V3z" clipRule="evenodd" />
          </svg>
        </button>
      </div>

      {selectedNode && nodeMetadata && (
        <div className="metadata-popup" data-testid="node-metadata-popup">
          <div className="metadata-popup-header">
            <h3>{selectedNode.entity_type || 'Node Details'}</h3>
            <button className="close-btn" onClick={() => focusNode(null)} data-testid="close-popup-btn">
              <svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
          <div className="metadata-popup-body">
            {nodeMetadataLoading ? (
              <p className="loading-msg">Loading metadata...</p>
            ) : (
              <>
                <div className="metadata-row">
                  <div className="metadata-label">Entity:</div>
                  <div className="metadata-value">{nodeMetadata.entity_type || 'N/A'}</div>
                </div>
                {Object.entries(nodeMetadata.properties || {}).map(([key, value]) => (
                  <div className="metadata-row" key={key}>
                    <div className="metadata-label">{formatLabel(key)}:</div>
                    <div className="metadata-value">{formatValue(value)}</div>
                  </div>
                ))}
              </>
            )}
          </div>
          <div className="metadata-footer">
            <div className="connections-count">
              Connections: {selectedNode.relationship_count || 0}
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

// Fetch metadata for selected nodes
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

// Helper functions
function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function formatValue(value: any): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}