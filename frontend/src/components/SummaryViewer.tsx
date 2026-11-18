import React, { useEffect, useState } from 'react'
import {
  BookOpen,
  Copy,
  Check,
  Loader2,
  AlertTriangle,
  Download,
  RefreshCw,
  History,
  RotateCcw,
} from 'lucide-react'
import { apiClient } from '../api/client'
import { DocumentItem, SummaryVersion } from '../types'

interface SummaryViewerProps {
  document: DocumentItem
  onUpdated: () => void
}

export const SummaryViewer: React.FC<SummaryViewerProps> = ({ document, onUpdated }) => {
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [versions, setVersions] = useState<SummaryVersion[]>([])
  const [showVersions, setShowVersions] = useState(false)
  const [streamingSummary, setStreamingSummary] = useState<string | null>(null)

  const loadVersions = async () => {
    try {
      setVersions(await apiClient.listVersions(document.id))
    } catch {
      // история не критична для просмотра
    }
  }

  useEffect(() => {
    if (document.status === 'completed') loadVersions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [document.id, document.status])

  const handleCopy = () => {
    if (!document.summary) return
    navigator.clipboard.writeText(document.summary)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExport = async (format: 'md' | 'docx' | 'pdf') => {
    setBusy(true)
    setError(null)
    try {
      await apiClient.downloadSummary(document.id, format)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка экспорта')
    } finally {
      setBusy(false)
    }
  }

  const handleRegenerate = async () => {
    setBusy(true)
    setError(null)
    setStreamingSummary('')
    try {
      // S3-08: токены конспекта приходят по SSE
      await apiClient.regenerateSummaryStream(document.id, {
        onToken: (delta) => setStreamingSummary((prev) => (prev ?? '') + delta),
      })
      onUpdated()
      await loadVersions()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка генерации')
    } finally {
      setBusy(false)
      setStreamingSummary(null)
    }
  }

  const handleRestore = async (versionId: string) => {
    setBusy(true)
    setError(null)
    try {
      await apiClient.restoreVersion(document.id, versionId)
      onUpdated()
      await loadVersions()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка восстановления')
    } finally {
      setBusy(false)
    }
  }

  if (
    document.status === 'pending' ||
    document.status === 'processing' ||
    document.status === 'embedding'
  ) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16 px-4 text-center">
        <div className="w-12 h-12 rounded-full bg-indigo-50 flex items-center justify-center mb-4">
          <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">ИИ изучает ваш документ...</h3>
        <p className="text-sm text-slate-500 max-w-md mt-1">
          Извлекаем текст, разбиваем его на смысловые фрагменты и формируем структурированный
          конспект.
        </p>
      </div>
    )
  }

  if (document.status === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16 px-4 text-center">
        <div className="w-12 h-12 rounded-full bg-rose-50 flex items-center justify-center mb-4">
          <AlertTriangle className="w-6 h-6 text-rose-600" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">Не удалось обработать документ</h3>
        <p className="text-sm text-slate-500 max-w-md mt-1">
          Проверьте корректность файла или настройки API-ключа на сервере.
        </p>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      {error && (
        <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 bg-slate-50/70 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-slate-800 font-semibold">
            <BookOpen className="w-5 h-5 text-indigo-600" />
            <span>Умный конспект документа</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleCopy}
              disabled={!document.summary}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-600" /> Скопировано
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" /> Копировать
                </>
              )}
            </button>
            <button
              onClick={handleRegenerate}
              disabled={busy}
              title="Пересоздать конспект"
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} /> Обновить
            </button>
            {(['md', 'docx', 'pdf'] as const).map((format) => (
              <button
                key={format}
                onClick={() => handleExport(format)}
                disabled={busy || !document.summary}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-700 bg-indigo-50 border border-indigo-100 px-3 py-1.5 rounded-lg disabled:opacity-50"
              >
                <Download className="w-3.5 h-3.5" /> {format.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        <div className="p-6 text-slate-700 leading-relaxed whitespace-pre-wrap text-sm md:text-base">
          {streamingSummary ?? document.summary ?? 'Конспект отсутствует.'}
          {streamingSummary !== null && (
            <span className="inline-block w-1.5 h-4 ml-1 align-middle bg-indigo-500 animate-pulse" />
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <button
          onClick={() => setShowVersions(!showVersions)}
          className="w-full flex items-center justify-between px-6 py-4 text-sm font-semibold text-slate-800"
        >
          <span className="inline-flex items-center gap-2">
            <History className="w-4 h-4 text-indigo-600" /> История версий ({versions.length})
          </span>
          <span className="text-slate-400">{showVersions ? '−' : '+'}</span>
        </button>
        {showVersions && (
          <div className="border-t border-slate-200 px-6 py-3 space-y-2">
            {versions.length === 0 ? (
              <p className="text-sm text-slate-400 py-2">Версий пока нет.</p>
            ) : (
              versions.map((v) => (
                <div
                  key={v.id}
                  className="flex items-start justify-between gap-3 py-2 border-b border-slate-100 last:border-0"
                >
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-slate-600">
                      Версия {v.version} · {new Date(v.created_at).toLocaleString('ru-RU')}
                    </div>
                    <div className="text-xs text-slate-400 truncate mt-0.5">
                      {v.summary.slice(0, 120)}
                    </div>
                  </div>
                  <button
                    onClick={() => handleRestore(v.id)}
                    disabled={busy}
                    title="Восстановить эту версию"
                    className="shrink-0 p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-md"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
