import React, { useEffect, useState } from 'react'
import { FileImage, Loader2 } from 'lucide-react'
import { apiClient } from '../api/client'
import { PageItem } from '../types'

interface PagesViewerProps {
  documentId: string
  focusedPage: number | null
}

export const PagesViewer: React.FC<PagesViewerProps> = ({ documentId, focusedPage }) => {
  const [pages, setPages] = useState<PageItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    apiClient
      .getPages(documentId)
      .then((data) => {
        if (!cancelled) setPages(data)
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [documentId])

  useEffect(() => {
    if (focusedPage) {
      document.getElementById(`page-${focusedPage}`)?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [focusedPage, pages])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-slate-500 text-sm">
        <Loader2 className="w-4 h-4 animate-spin mr-2" /> Загрузка страниц...
      </div>
    )
  }
  if (error) return <div className="p-6 text-sm text-rose-600">{error}</div>
  if (pages.length === 0) {
    return (
      <div className="p-6 text-sm text-slate-500">
        Постраничный текст недоступен для этого файла.
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      {pages.map((page) => (
        <section
          id={`page-${page.page_number}`}
          key={page.page_number}
          aria-label={`Страница ${page.page_number}`}
          className={`bg-white rounded-xl border p-5 shadow-xs ${
            focusedPage === page.page_number
              ? 'border-indigo-400 ring-2 ring-indigo-100'
              : 'border-slate-200'
          }`}
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-800">
              <FileImage className="w-4 h-4 text-indigo-600" /> Страница {page.page_number}
            </h3>
            <span className="text-[11px] text-slate-400">
              {page.extraction_method} · confidence {page.confidence}%
            </span>
          </div>
          <p className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed">{page.text}</p>
        </section>
      ))}
    </div>
  )
}
