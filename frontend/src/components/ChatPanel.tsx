import { useState } from 'react'
import { MessageHistory } from './MessageHistory'
import { useChat } from '../hooks/useChat'
import { useGraphContext } from '../contexts/GraphContext'

export function ChatPanel() {
  const { messages, loading, error, sendMessage } = useChat()
  const [input, setInput] = useState('')
  const { onEntityReference } = useGraphContext()

  const submit = async () => {
    if (!input.trim() || loading) return
    const value = input
    setInput('')
    const entities = await sendMessage(value)
    if (entities && entities.length > 0) {
      await onEntityReference(entities[0].id)
    }
  }

  return (
    <section className="panel">
      <h2>Chat</h2>
      {error && <p className="error-text">{error}</p>}
      <div className="messages-wrap">
        <MessageHistory messages={messages} loading={loading} />
      </div>
      <div className="input-row">
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && submit()}
          placeholder="Ask a question about your data..."
        />
        <button onClick={submit} disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </div>
    </section>
  )
}
