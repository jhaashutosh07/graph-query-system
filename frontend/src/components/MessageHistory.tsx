import type { Message } from '../types'

interface MessageHistoryProps {
  messages: Message[]
  loading: boolean
}

export function MessageHistory({ messages, loading }: MessageHistoryProps) {
  return (
    <>
      {messages.map((msg, index) => (
        <div 
          key={index} 
          className={`message ${msg.role}`}
          data-testid={`message-${msg.role}`}
        >
          <div className="message-avatar">
            {msg.role === 'assistant' ? 'D' : '👤'}
          </div>
          <div className="message-content">
            {msg.content}
          </div>
        </div>
      ))}
      {loading && (
        <div className="message assistant" data-testid="loading-message">
          <div className="message-avatar">D</div>
          <div className="message-content">
            <span className="loading-msg">Analyzing...</span>
          </div>
        </div>
      )}
    </>
  )
}