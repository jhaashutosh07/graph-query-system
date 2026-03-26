import type { Message } from '../types'

export function MessageHistory({ messages, loading }: { messages: Message[]; loading: boolean }) {
  if (messages.length === 0) {
    return (
      <div className="empty-state">
        <h3>Start asking questions</h3>
        <p>Try:</p>
        <ul>
          <li>Which products are in the most orders?</li>
          <li>Trace order ORD-001 through invoice and payment</li>
          <li>Find delivered orders with no invoice</li>
        </ul>
      </div>
    )
  }

  return (
    <div className="messages-list">
      {messages.map((message, index) => (
        <div key={`${message.timestamp}-${index}`} className={`message ${message.role}`}>
          <strong>{message.role === 'user' ? 'You' : 'Assistant'}:</strong> {message.content}
        </div>
      ))}
      {loading && <div className="loading-msg">Loading...</div>}
    </div>
  )
}
