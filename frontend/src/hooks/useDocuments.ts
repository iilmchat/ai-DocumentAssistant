import { useState, useEffect, useCallback } from 'react'
import { DocumentItem } from '../types'
import { apiClient } from '../api/client'

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDocuments = useCallback(async () => {
    try {
      const data = await apiClient.getDocuments()
      setDocuments(data.items)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Сервер API недоступен')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchDocuments()
  }, [fetchDocuments])

  useEffect(() => {
    const hasPendingDocs = documents.some(
      (doc) => doc.status === 'pending' || doc.status === 'processing' || doc.status === 'embedding'
    )

    if (!hasPendingDocs) return

    const interval = setInterval(() => {
      fetchDocuments()
    }, 3000)

    return () => clearInterval(interval)
  }, [documents, fetchDocuments])

  const uploadFile = async (file: File): Promise<DocumentItem | null> => {
    setIsUploading(true)
    setError(null)
    try {
      const newDoc = await apiClient.uploadDocument(file)
      setDocuments((prev) => [newDoc, ...prev])
      return newDoc
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка загрузки файла')
      return null
    } finally {
      setIsUploading(false)
    }
  }

  const removeDocument = async (id: string) => {
    try {
      await apiClient.deleteDocument(id)
      setDocuments((prev) => prev.filter((doc) => doc.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка удаления')
    }
  }

  return {
    documents,
    isLoading,
    isUploading,
    error,
    uploadFile,
    removeDocument,
    refresh: fetchDocuments,
  }
}
