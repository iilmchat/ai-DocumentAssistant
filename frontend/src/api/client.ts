import {
  AuthResponse,
  DocumentItem,
  ChatResponse,
  SourceCitation,
  SummaryVersion,
  UserInfo,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''
const TOKEN_KEY = 'ai_document_assistant_token'

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

function authHeaders(): Record<string, string> {
  const token = tokenStore.get()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function handleUnauthorized(response: Response): void {
  if (response.status === 401) {
    tokenStore.clear()
    window.dispatchEvent(new Event('auth:logout'))
  }
}

export const apiClient = {
  async register(email: string, password: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || 'Не удалось зарегистрироваться')
    }
    return response.json()
  },

  async login(email: string, password: string): Promise<AuthResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || 'Не удалось войти')
    }
    return response.json()
  },

  async getCurrentUser(): Promise<UserInfo> {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: authHeaders(),
    })
    if (!response.ok) throw new Error('Сессия истекла')
    return response.json()
  },

  async getDocuments(): Promise<DocumentItem[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/`, {
      headers: authHeaders(),
    })
    if (!response.ok) {
      handleUnauthorized(response)
      throw new Error('Не удалось загрузить список документов')
    }
    return response.json()
  },

  async uploadDocument(file: File): Promise<DocumentItem> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData,
    })

    if (!response.ok) {
      handleUnauthorized(response)
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || 'Ошибка при загрузке документа')
    }
    return response.json()
  },

  async deleteDocument(documentId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    if (!response.ok) {
      handleUnauthorized(response)
      throw new Error('Не удалось удалить документ')
    }
  },

  /** Этап 7: скачать конспект в нужном формате. */
  async downloadSummary(documentId: string, format: 'md' | 'docx' | 'pdf'): Promise<void> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/documents/${documentId}/export?format=${format}`,
      { headers: authHeaders() }
    )
    if (!response.ok) {
      handleUnauthorized(response)
      throw new Error('Не удалось скачать конспект')
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const match = disposition.match(/filename="?([^";]+)"?/)
    link.download = match?.[1] ?? `summary.${format}`
    window.document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },

  async listVersions(documentId: string): Promise<SummaryVersion[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/versions`, {
      headers: authHeaders(),
    })
    if (!response.ok) {
      handleUnauthorized(response)
      throw new Error('Не удалось загрузить историю версий')
    }
    return response.json()
  },

  async regenerateSummary(documentId: string): Promise<SummaryVersion> {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}/summarize`, {
      method: 'POST',
      headers: authHeaders(),
    })
    if (!response.ok) {
      handleUnauthorized(response)
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || 'Не удалось пересоздать конспект')
    }
    return response.json()
  },

  async restoreVersion(documentId: string, versionId: string): Promise<DocumentItem> {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/documents/${documentId}/versions/${versionId}/restore`,
      { method: 'POST', headers: authHeaders() }
    )
    if (!response.ok) {
      handleUnauthorized(response)
      throw new Error('Не удалось восстановить версию')
    }
    return response.json()
  },

  async askQuestion(
    documentId: string,
    question: string,
    signal?: AbortSignal
  ): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
      },
      body: JSON.stringify({
        document_id: documentId,
        question,
      }),
      signal,
    })

    if (!response.ok) {
      handleUnauthorized(response)
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || 'Ошибка при получении ответа от ИИ')
    }
    return response.json()
  },

  /**
   * Этап 6: реальный стриминг ответа через SSE.
   * События: citations -> token* -> done / error.
   */
  async streamAnswer(
    documentId: string,
    question: string,
    callbacks: {
      onToken: (delta: string) => void
      onCitations: (citations: SourceCitation[]) => void
      onError?: (message: string) => void
    },
    signal?: AbortSignal
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ document_id: documentId, question }),
      signal,
    })

    if (!response.ok || !response.body) {
      handleUnauthorized(response)
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || 'Не удалось получить поток ответа')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    let finished = false
    while (!finished) {
      const { done, value } = await reader.read()
      finished = done
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''

      for (const frame of frames) {
        let event = 'message'
        let data = ''
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (!data) continue
        try {
          const payload = JSON.parse(data)
          if (event === 'token') {
            callbacks.onToken(payload.delta ?? '')
          } else if (event === 'citations') {
            callbacks.onCitations(payload as SourceCitation[])
          } else if (event === 'error') {
            callbacks.onError?.(
              typeof payload === 'string' ? payload : (payload.message ?? 'Ошибка генерации')
            )
          }
        } catch {
          // битый кадр — пропускаем, поток продолжаем
        }
      }
    }
  },
}
