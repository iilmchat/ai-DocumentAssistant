export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface DocumentItem {
  id: string;
  title: string;
  status: DocumentStatus;
  summary: string | null;
  created_at: string;
}

export interface ChatResponse {
  answer: string;
  sources: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  isStreaming?: boolean;
  error?: boolean;
}
