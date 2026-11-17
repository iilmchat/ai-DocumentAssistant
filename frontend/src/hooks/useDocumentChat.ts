import { useState, useRef, useCallback, useEffect } from 'react';
import { ChatMessage } from '../types';
import { apiClient } from '../api/client';

export function useDocumentChat(documentId: string | null) {
  const [messagesByDoc, setMessagesByDoc] = useState<Record<string, ChatMessage[]>>({});
  const [isSending, setIsSending] = useState<boolean>(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const typewriterTimerRef = useRef<number | null>(null);

  const messages = documentId ? messagesByDoc[documentId] || [] : [];

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (typewriterTimerRef.current) {
      window.clearInterval(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    setIsSending(false);
    if (documentId) {
      setMessagesByDoc((prev) => ({
        ...prev,
        [documentId]: (prev[documentId] || []).map((m) =>
          m.isStreaming ? { ...m, isStreaming: false } : m
        ),
      }));
    }
  }, [documentId]);

  useEffect(() => {
    return () => {
      stopGeneration();
    };
  }, [documentId, stopGeneration]);

  const sendMessage = async (question: string) => {
    if (!documentId || !question.trim() || isSending) return;

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question.trim(),
    };

    const assistantMsgId = crypto.randomUUID();
    const placeholderMessage: ChatMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    setMessagesByDoc((prev) => ({
      ...prev,
      [documentId]: [...(prev[documentId] || []), userMessage, placeholderMessage],
    }));

    setIsSending(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await apiClient.askQuestion(documentId, question.trim(), controller.signal);
      const fullText = response.answer;
      let currentIndex = 0;

      // Плавный typewriter-эффект вывода текста
      typewriterTimerRef.current = window.setInterval(() => {
        currentIndex += 3;
        const slice = fullText.slice(0, currentIndex);
        const done = currentIndex >= fullText.length;

        setMessagesByDoc((prev) => ({
          ...prev,
          [documentId]: (prev[documentId] || []).map((msg) =>
            msg.id === assistantMsgId
              ? {
                  ...msg,
                  content: slice,
                  sources: done ? response.sources : undefined,
                  isStreaming: !done,
                }
              : msg
          ),
        }));

        if (done) {
          if (typewriterTimerRef.current) {
            window.clearInterval(typewriterTimerRef.current);
            typewriterTimerRef.current = null;
          }
          setIsSending(false);
          abortControllerRef.current = null;
        }
      }, 15);
    } catch (err) {
      if ((err as Error).name === 'AbortError') return;
      setMessagesByDoc((prev) => ({
        ...prev,
        [documentId]: (prev[documentId] || []).map((msg) =>
          msg.id === assistantMsgId
            ? {
                ...msg,
                content: err instanceof Error ? err.message : 'Произошла ошибка при запросе.',
                isStreaming: false,
                error: true,
              }
            : msg
        ),
      }));
      setIsSending(false);
    }
  };

  return {
    messages,
    isSending,
    sendMessage,
    stopGeneration,
  };
}
