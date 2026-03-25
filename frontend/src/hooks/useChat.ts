import { useState } from 'react'
import { queryGraph } from '../api/client'
import type { Message } from '../types'

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conversationId] = useState<string>(() => crypto.randomUUID())

  const sendMessage = async (query: string) => {
    const trimmed = query.trim()
    if (!trimmed) return

    const userMessage: Message = {
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString()
    }
    setMessages((prev) => [...prev, userMessage])
    setLoading(true)
    setError(null)

    try {
      const response = await queryGraph({ query: trimmed, conversation_id: conversationId })
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.answer,
          referenced_entities: response.referenced_entities,
          timestamp: new Date().toISOString()
        }
      ])
      return response.referenced_entities
    } catch {
      setError('Failed to process query')
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Error processing query. Please try again.',
          timestamp: new Date().toISOString()
        }
      ])
      return []
    } finally {
      setLoading(false)
    }
  }

  return { messages, loading, error, sendMessage }
}
