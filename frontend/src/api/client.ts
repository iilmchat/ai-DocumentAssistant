import {
  AuthResponse,
  DocumentItem,
  DocumentList,
  ChatResponse,
  SourceCitation,
  SummaryVersion,
  UserInfo,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''
const TOKEN_KEY = 'ai_document_assistant_token'
const REFRESH_KEY = 'ai_document_assistant_refresh'

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  getRefresh: (): string | null => localStorage.getItem(REFRESH_KEY),
  setRefresh: (token: string) => localStorage.setItem(REFRESH_KEY, token),
  setPair: (pair: AuthResponse) => {
    tokenStore.set(pair.access_token)
    tokenStore.setRefresh(pair.refresh_token)
  },
  clear: () => localStorage.removeItem(TOKEN_KEY),
  clearRefresh: () => localStorage.removeItem(REFRESH_KEY),
  clearAll: () => {
    tokenStore.clear()
    tokenStore.clearRefresh()
  },
}

function authHeaders(): Record<string, string> {
  const token = tokenStore.get()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function handleUnauthorized(response: Response): void {
  if (response.status === 401) {
    tokenStore.clearAll()
    window.dispatchEvent(new Event('auth:logout'))
  }
}

let refreshInFlight: Promise<boolean> | null = null

/** S1: бесшовное обновление access-токена через refresh (ротация на бэке). */
export async function refreshTokens(): Promise<boolean> {
  const refresh = tokenStore.getRefresh()
  if (!refresh) return false
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        })
        if (!response.ok) return false
        tokenStore.setPair((await response.json()) as AuthResponse)
        return true
      } catch {
        return false
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

/** Обёртка: при 401 один раз обновляет токен и повторяет запрос. */
async function authFetch(url: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const response = await fetch(url, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers as Record<string, string>) },
  })
  if (response.status === 401 && retry && tokenStore.getRefresh()) {
    const refreshed = await refreshTokens()
    if (refreshed) return authFetch(url, init, false)
  }
  if (response.status === 401) handleUnauthorized(response)
  return response
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

  async logout(): Promise<void> {
    try {
      await authFetch(`${API_BASE_URL}/api/v1/auth/logout`, { method: 'POST' })
    } finally {
      tokenStore.clearAll()
    }
  },

  async getCurrentUser(): Promise<UserInfo> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/auth/me`)
    if (!response.ok) throw new Error('Сессия истекла')
    return response.json()
  },

  async getDocuments(limit = 100): Promise<DocumentList> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/?limit=${limit}`)
    if (!response.ok) throw new Error('Не удалось загрузить список документов')
    return response.json()
  },

  async uploadDocument(file: File): Promise<DocumentItem> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/upload`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}))
      throw new Error(errData.detail || 'Ошибка при загрузке документа')
    }
    return response.json()
  },

  async deleteDocument(documentId: string): Promise<void> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/${documentId}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('Не удалось удалить документ')
  },

  /** Этап 7: скачать конспект в нужном формате. */
  async downloadSummary(documentId: string, format: 'md' | 'docx' | 'pdf'): Promise<void> {
    const response = await authFetch(
      `${API_BASE_URL}/api/v1/documents/${documentId}/export?format=${format}`
    )
    if (!response.ok) throw new Error('Не удалось скачать конспект')
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
    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/versions`)
    if (!response.ok) throw new Error('Не удалось загрузить историю версий')
    return response.json()
  },

  async regenerateSummary(documentId: string): Promise<SummaryVersion> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/summarize`, {
      method: 'POST',
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || 'Не удалось пересоздать конспект')
    }
    return response.json()
  },

  /** S3-08: стриминг генерации конспекта. */
  async regenerateSummaryStream(
    documentId: string,
    callbacks: { onToken: (delta: string) => void; onDone?: () => void },
    signal?: AbortSignal
  ): Promise<void> {
    const response = await authFetch(
      `${API_BASE_URL}/api/v1/documents/${documentId}/summarize/stream`,
      { method: 'POST', signal }
    )
    if (!response.ok || !response.body) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || 'Не удалось сгенерировать конспект')
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
          if (event === 'token') callbacks.onToken(payload.delta ?? '')
          else if (event === 'done') callbacks.onDone?.()
          else if (event === 'error') throw new Error(payload.message ?? 'Ошибка генерации')
        } catch (err) {
          if (err instanceof SyntaxError) continue
          throw err
        }
      }
    }
  },

  async restoreVersion(documentId: string, versionId: string): Promise<DocumentItem> {
    const response = await authFetch(
      `${API_BASE_URL}/api/v1/documents/${documentId}/versions/${versionId}/restore`,
      { method: 'POST' }
    )
    if (!response.ok) throw new Error('Не удалось восстановить версию')
    return response.json()
  },

  async askQuestion(
    documentId: string,
    question: string,
    signal?: AbortSignal
  ): Promise<ChatResponse> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/chat/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_id: documentId, question }),
      signal,
    })

    if (!response.ok) {
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
    const response = await authFetch(`${API_BASE_URL}/api/v1/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_id: documentId, question }),
      signal,
    })

    if (!response.ok || !response.body) {
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
