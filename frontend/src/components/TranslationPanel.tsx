import React, { useEffect, useState } from 'react'
import { Languages, Loader2, Trash2, AlertCircle, Plus, BookMarked, Download } from 'lucide-react'
import { apiClient } from '../api/client'
import { TranslationStatus, GlossaryTerm } from '../types'
import { useI18n } from '../i18n'

interface TranslationPanelProps {
  documentId: string
  sourceLanguage: string | null
  onChanged: () => void
}

const LANGUAGES = ['ru', 'en', 'de', 'fr', 'es']

export const TranslationPanel: React.FC<TranslationPanelProps> = ({
  documentId,
  sourceLanguage,
  onChanged,
}) => {
  const { t } = useI18n()
  const [target, setTarget] = useState('ru')
  const [status, setStatus] = useState<TranslationStatus | null>(null)
  const [glossary, setGlossary] = useState<GlossaryTerm[]>([])
  const [sourceTerm, setSourceTerm] = useState('')
  const [targetTerm, setTargetTerm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    try {
      setStatus(await apiClient.getTranslationStatus(documentId))
      setGlossary(await apiClient.getGlossary(documentId))
    } catch {
      // статус не критичен
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documentId])

  const poll = status?.status === 'pending'
  useEffect(() => {
    if (!poll) return
    const timer = window.setInterval(() => void load(), 3000)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [poll, documentId])

  const handleTranslate = async () => {
    setBusy(true)
    setError(null)
    try {
      await apiClient.translateDocument(documentId, target)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка перевода')
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    setBusy(true)
    try {
      await apiClient.deleteTranslation(documentId)
      await load()
      onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка удаления перевода')
    } finally {
      setBusy(false)
    }
  }

  const handleAddTerm = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sourceTerm.trim() || !targetTerm.trim()) return
    setBusy(true)
    try {
      await apiClient.addGlossaryTerm(documentId, sourceTerm.trim(), targetTerm.trim(), target)
      setSourceTerm('')
      setTargetTerm('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка добавления термина')
    } finally {
      setBusy(false)
    }
  }

  const progress = status?.total_chunks
    ? Math.round((status.translated_chunks / status.total_chunks) * 100)
    : 0

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6">
        <div className="flex items-center gap-2 text-slate-800 font-semibold mb-4">
          <Languages className="w-5 h-5 text-indigo-600" />
          {t('translation')}
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2 mb-4">
            <AlertCircle className="w-4 h-4 shrink-0" /> {error}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm text-slate-600" htmlFor="target-language">
            {t('targetLang')}:
          </label>
          <select
            id="target-language"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-2 text-sm"
          >
            {LANGUAGES.filter((lang) => lang !== sourceLanguage).map((lang) => (
              <option key={lang} value={lang}>
                {lang.toUpperCase()}
              </option>
            ))}
          </select>
          <button
            onClick={handleTranslate}
            disabled={busy || poll}
            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white px-4 py-2 rounded-lg text-sm"
          >
            {busy || poll ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Languages className="w-4 h-4" />
            )}
            {poll ? t('translating') : t('startTranslation')}
          </button>
          {status?.status === 'completed' && (
            <>
              {(['md', 'docx', 'pdf'] as const).map((format) => (
                <button
                  key={format}
                  onClick={() => void apiClient.downloadTranslation(documentId, format)}
                  disabled={busy}
                  className="inline-flex items-center gap-1.5 text-indigo-600 border border-indigo-200 px-3 py-2 rounded-lg text-xs"
                >
                  <Download className="w-3.5 h-3.5" /> {format.toUpperCase()}
                </button>
              ))}
              <button
                onClick={handleDelete}
                disabled={busy}
                className="inline-flex items-center gap-2 text-rose-600 border border-rose-200 px-3 py-2 rounded-lg text-sm"
              >
                <Trash2 className="w-4 h-4" /> {t('deleteTranslation')}
              </button>
            </>
          )}
        </div>

        {status && status.total_chunks > 0 && (
          <div className="mt-4">
            <div className="text-xs text-slate-500 mb-1">
              {status.translated_chunks} / {status.total_chunks} · {progress}%
            </div>
            <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-4">
          {t('machineTranslation')}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6">
        <div className="flex items-center gap-2 text-slate-800 font-semibold mb-4">
          <BookMarked className="w-5 h-5 text-indigo-600" />
          {t('glossary')}
        </div>
        <form onSubmit={handleAddTerm} className="flex flex-wrap gap-2 mb-4">
          <input
            value={sourceTerm}
            onChange={(e) => setSourceTerm(e.target.value)}
            placeholder={t('sourceTerm')}
            aria-label={t('sourceTerm')}
            className="flex-1 min-w-40 border border-slate-200 rounded-lg px-3 py-2 text-sm"
          />
          <input
            value={targetTerm}
            onChange={(e) => setTargetTerm(e.target.value)}
            placeholder={t('targetTerm')}
            aria-label={t('targetTerm')}
            className="flex-1 min-w-40 border border-slate-200 rounded-lg px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={busy}
            className="inline-flex items-center gap-1.5 bg-slate-800 text-white px-3 py-2 rounded-lg text-sm"
          >
            <Plus className="w-4 h-4" /> {t('addTerm')}
          </button>
        </form>
        {glossary.length === 0 ? (
          <p className="text-sm text-slate-400">—</p>
        ) : (
          <ul className="space-y-1.5">
            {glossary.map((term) => (
              <li
                key={term.id}
                className="flex items-center justify-between text-sm border-b border-slate-100 py-1.5"
              >
                <span className="text-slate-700">{term.source_term}</span>
                <span className="text-indigo-600">→ {term.target_term}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
