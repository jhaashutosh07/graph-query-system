import { createContext, useContext } from 'react'
import type { GraphNode } from '../types'
import { useGraph } from '../hooks/useGraph'

type GraphContextValue = ReturnType<typeof useGraph> & {
  onEntityReference: (entityId: string) => Promise<void>
}

const GraphContext = createContext<GraphContextValue | null>(null)

export function GraphProvider({ children }: { children: React.ReactNode }) {
  const graphState = useGraph()

  const onEntityReference = async (entityId: string) => {
    const node = graphState.graph.nodes.find((item) => item.id === entityId) as GraphNode | undefined
    if (node) {
      await graphState.focusNode(node)
    }
  }

  return (
    <GraphContext.Provider value={{ ...graphState, onEntityReference }}>
      {children}
    </GraphContext.Provider>
  )
}

export function useGraphContext() {
  const context = useContext(GraphContext)
  if (!context) {
    throw new Error('useGraphContext must be used within GraphProvider')
  }
  return context
}
