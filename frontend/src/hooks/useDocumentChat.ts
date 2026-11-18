import { useState, useRef, useCallback, useEffect } from 'react'
import { ChatMessage } from '../types'
import { apiClient } from '../api/client'

export function useDocumentChat(documentId: string | null) {
  const [messagesByDoc, setMessagesByDoc] = useState<Record<string, ChatMessage[]>>({})
  const [isSending, setIsSending] = useState<boolean>(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const messages = documentId ? messagesByDoc[documentId] || [] : []

  const updateAssistantMessage = useCallback(
    (docId: string, id: string, patch: Partial<ChatMessage>) => {
      setMessagesByDoc((prev) => ({
        ...prev,
        [docId]: (prev[docId] || []).map((m) => (m.id === id ? { ...m, ...patch } : m)),
      }))
    },
    []
  )

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsSending(false)
    if (documentId) {
      setMessagesByDoc((prev) => ({
        ...prev,
        [documentId]: (prev[documentId] || []).map((m) =>
          m.isStreaming ? { ...m, isStreaming: false } : m
        ),
      }))
    }
  }, [documentId])

  useEffect(() => {
    return () => {
      stopGeneration()
    }
  }, [documentId, stopGeneration])

  const sendMessage = async (question: string) => {
    if (!documentId || !question.trim() || isSending) return
    const docId = documentId

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question.trim(),
    }

    const assistantMsgId = crypto.randomUUID()
    const placeholderMessage: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    }

    setMessagesByDoc((prev) => ({
      ...prev,
      [docId]: [...(prev[docId] || []), userMessage, placeholderMessage],
    }))

    setIsSending(true)
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      // Этап 6: токены приходят по SSE, имитация «печатной машинки» удалена
      await apiClient.streamAnswer(
        docId,
        question.trim(),
        {
          onCitations: (citations) => {
            updateAssistantMessage(docId, assistantMsgId, { citations })
          },
          onToken: (delta) => {
            setMessagesByDoc((prev) => ({
              ...prev,
              [docId]: (prev[docId] || []).map((m) =>
                m.id === assistantMsgId ? { ...m, content: m.content + delta } : m
              ),
            }))
          },
          onError: (message) => {
            updateAssistantMessage(docId, assistantMsgId, {
              content: message,
              isStreaming: false,
              error: true,
            })
          },
        },
        controller.signal
      )
      updateAssistantMessage(docId, assistantMsgId, { isStreaming: false })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      updateAssistantMessage(docId, assistantMsgId, {
        content: err instanceof Error ? err.message : 'Произошла ошибка при запросе.',
        isStreaming: false,
        error: true,
      })
    } finally {
      setIsSending(false)
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null
      }
    }
  }

  return {
    messages,
    isSending,
    sendMessage,
    stopGeneration,
  }
}
