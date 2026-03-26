import { useState, useRef, useEffect } from 'react'
import { MessageHistory } from './MessageHistory'
import { useChat } from '../hooks/useChat'
import { useGraphContext } from '../contexts/GraphContext'

export function ChatPanel() {
  const { messages, loading, error, sendMessage } = useChat()
  const [input, setInput] = useState('')
  const { onEntityReference } = useGraphContext()
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const submit = async () => {
    if (!input.trim() || loading) return
    const value = input
    setInput('')
    const entities = await sendMessage(value)
    if (entities && entities.length > 0) {
      await onEntityReference(entities[0].id)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <section className="chat-panel" data-testid="chat-panel">
      <div className="chat-header">
        <div className="chat-title">Chat with Graph</div>
        <div className="chat-subtitle">Order to Cash</div>
      </div>

      <div className="ai-agent-intro">
        <div className="ai-avatar" data-testid="ai-avatar">D</div>
        <div className="ai-intro-text">
          <div className="ai-name">Dodge AI</div>
          <div className="ai-role">Graph Agent</div>
          <div className="ai-welcome">
            Hi! I can help you analyze the Order to Cash process.
          </div>
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      <div className="messages-container" data-testid="messages-container">
        <MessageHistory messages={messages} loading={loading} />
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-status">
        <div className="status-indicator" data-testid="status-indicator">
          <span className="status-dot"></span>
          <span>{loading ? 'Dodge AI is thinking...' : 'Dodge AI is awaiting instructions'}</span>
        </div>
      </div>

      <div className="chat-input-area">
        <div className="input-wrapper">
          <input
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Analyze anything"
            disabled={loading}
            data-testid="chat-input"
          />
          <button 
            className="send-btn" 
            onClick={submit} 
            disabled={loading || !input.trim()}
            data-testid="send-btn"
          >
            Send
          </button>
        </div>
      </div>
    </section>
  )
}