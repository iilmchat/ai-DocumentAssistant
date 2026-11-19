import {
  AuthResponse,
  DocumentItem,
  DocumentList,
  GlossaryTerm,
  PageItem,
  TranslationStatus,
  ChatResponse,
  SourceCitation,
  SummaryVersion,
  UserInfo,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''
const CSRF_COOKIE = 'csrf_token'

/**
 * T8: токены больше не хранятся в localStorage — они живут в httpOnly cookie.
 * Остаётся только не-httpOnly CSRF-cookie, которое JS копирует в заголовок.
 */
export const tokenStore = {
  get: (): string | null => null, // обратная совместимость вызовов
  clearAll: () => undefined,
}

function getCsrfToken(): string | null {
  return (
    document.cookie
      .split('; ')
      .find((c) => c.startsWith(`${CSRF_COOKIE}=`))
      ?.split('=')[1] ?? null
  )
}

function safeHeaders(init: RequestInit): Record<string, string> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) }
  const method = (init.method ?? 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrf = getCsrfToken()
    if (csrf) headers['X-CSRF-Token'] = csrf
  }
  return headers
}

function handleUnauthorized(response: Response): void {
  if (response.status === 401) {
    window.dispatchEvent(new Event('auth:logout'))
  }
}

let refreshInFlight: Promise<boolean> | null = null

/** Бесшовное обновление сессии: refresh-токен уходит автоматически в cookie. */
export async function refreshTokens(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
          headers: safeHeaders({ method: 'POST' }),
        })
        return response.ok
      } catch {
        return false
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

/** Обёртка: cookie отправляются автоматически, при 401 — один refresh и повтор. */
async function authFetch(url: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const response = await fetch(url, {
    ...init,
    credentials: 'include',
    headers: safeHeaders(init),
  })
  if (response.status === 401 && retry) {
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
      credentials: 'include',
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
      credentials: 'include',
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

  async getPages(documentId: string): Promise<PageItem[]> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/pages`)
    if (!response.ok) throw new Error('Не удалось загрузить страницы')
    return response.json()
  },

  // --- T6: двуязычные документы ---
  async translateDocument(documentId: string, targetLanguage: string): Promise<void> {
    const response = await authFetch(
      `${API_BASE_URL}/api/v1/documents/${documentId}/translate?target_language=${targetLanguage}`,
      { method: 'POST' }
    )
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || 'Не удалось запустить перевод')
    }
  },

  async getTranslationStatus(documentId: string): Promise<TranslationStatus> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/translation`)
    if (!response.ok) throw new Error('Не удалось получить статус перевода')
    return response.json()
  },

  async deleteTranslation(documentId: string): Promise<void> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/translation`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('Не удалось удалить перевод')
  },

  async getGlossary(documentId: string): Promise<GlossaryTerm[]> {
    const response = await authFetch(`${API_BASE_URL}/api/v1/documents/${documentId}/glossary`)
    if (!response.ok) throw new Error('Не удалось загрузить глоссарий')
    return response.json()
  },

  async addGlossaryTerm(
    documentId: string,
    source: string,
    target: string,
    targetLanguage = 'ru'
  ): Promise<void> {
    const response = await authFetch(
      `${API_BASE_URL}/api/v1/documents/${documentId}/glossary` +
        `?source_term=${encodeURIComponent(source)}&target_term=${encodeURIComponent(target)}` +
        `&target_language=${targetLanguage}`,
      { method: 'POST' }
    )
    if (!response.ok) throw new Error('Не удалось добавить термин')
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

  /** T6: экспорт перевода. */
  async downloadTranslation(documentId: string, format: 'md' | 'docx' | 'pdf'): Promise<void> {
    const response = await authFetch(
      `${API_BASE_URL}/api/v1/documents/${documentId}/export?format=${format}&translated=true`
    )
    if (!response.ok) throw new Error('Не удалось скачать перевод')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url
    link.download = `translation.${format}`
    window.document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
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
