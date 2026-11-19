export type DocumentStatus = 'pending' | 'processing' | 'embedding' | 'completed' | 'failed'

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface SummaryVersion {
  id: string
  version: number
  summary: string
  created_at: string
}

export interface UserInfo {
  id: string
  email: string
  created_at: string
}

export interface DocumentItem {
  id: string
  title: string
  status: DocumentStatus
  summary: string | null
  created_at: string
  language?: string | null
  translation_language?: string | null
}

export interface PageItem {
  page_number: number
  text: string
  extraction_method: string
  confidence: number
  text_translated?: string | null
  translation_language?: string | null
}

export interface TranslationStatus {
  document_id: string
  source_language: string | null
  target_language: string | null
  status: 'pending' | 'completed' | 'failed'
  total_chunks: number
  translated_chunks: number
  failed_chunks: number
}

export interface GlossaryTerm {
  id: string
  source_term: string
  target_term: string
  source_language: string | null
  target_language: string | null
}

export interface DocumentList {
  items: DocumentItem[]
  total: number
  limit: number
  offset: number
}

export interface SourceCitation {
  page_numbers: number[]
  headings: string[]
  snippet: string
  extraction_method: string | null
}

export interface ChatResponse {
  answer: string
  sources: string[]
  citations: SourceCitation[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  citations?: SourceCitation[]
  isStreaming?: boolean
  error?: boolean
}
