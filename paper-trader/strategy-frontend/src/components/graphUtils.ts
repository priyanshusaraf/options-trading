import type { Connection } from '@xyflow/react'

export interface PendingConnection {
  nodeId: string
  nodeTitle: string
  handleId: string | null
  handleType: 'source' | 'target' | null
}

export function connectionForInsertedNode(connection: PendingConnection, nodeId: string): Connection {
  const fromTarget = connection.handleType === 'target'
  return {
    source: fromTarget ? nodeId : connection.nodeId,
    target: fromTarget ? connection.nodeId : nodeId,
    sourceHandle: fromTarget ? 'output' : connection.handleId ?? 'output',
    targetHandle: fromTarget ? connection.handleId ?? 'input-0' : 'input-0',
  }
}
