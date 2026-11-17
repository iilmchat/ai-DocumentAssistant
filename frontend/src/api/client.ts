import { DocumentItem, ChatResponse } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

export const apiClient = {
  async getDocuments(): Promise<DocumentItem[]> {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/`);
    if (!response.ok) {
      throw new Error('Не удалось загрузить список документов');
    }
    return response.json();
  },

  async uploadDocument(file: File): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || 'Ошибка при загрузке документа');
    }
    return response.json();
  },

  async deleteDocument(documentId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Не удалось удалить документ');
    }
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
      },
      body: JSON.stringify({
        document_id: documentId,
        question,
      }),
      signal,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || 'Ошибка при получении ответа от ИИ');
    }
    return response.json();
  },
};
