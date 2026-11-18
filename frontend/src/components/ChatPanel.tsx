import React, { useState, useRef, useEffect } from 'react'
import {
  Send,
  Square,
  Bot,
  User as UserIcon,
  Quote,
  ChevronDown,
  ChevronUp,
  Sparkles,
} from 'lucide-react'
import { ChatMessage, SourceCitation } from '../types'

interface ChatPanelProps {
  documentTitle: string
  disabled: boolean
  messages: ChatMessage[]
  isSending: boolean
  onSendMessage: (question: string) => void
  onStopGeneration: () => void
}

const SourceAccordion: React.FC<{ citations: SourceCitation[]; sources?: string[] }> = ({
  citations,
  sources,
}) => {
  const [open, setOpen] = useState(false)

  // Fallback для старого формата ответа без цитат
  const items: SourceCitation[] = citations?.length
    ? citations
    : (sources ?? []).map((snippet) => ({
        page_numbers: [],
        headings: [],
        snippet,
        extraction_method: null,
      }))

  if (items.length === 0) return null

  return (
    <div className="mt-3 pt-2.5 border-t border-slate-200/70">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-700"
      >
        <Quote className="w-3.5 h-3.5" />
        <span>Источники из документа ({items.length})</span>
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {items.map((citation, idx) => (
            <div
              key={idx}
              className="text-xs text-slate-600 bg-slate-50 border border-slate-200/80 rounded-lg p-2.5 leading-relaxed"
            >
              <div className="flex flex-wrap items-center gap-1.5 mb-1">
                <span className="font-semibold text-slate-400">#{idx + 1}</span>
                {citation.page_numbers.length > 0 && (
                  <span className="inline-flex items-center rounded bg-indigo-100 text-indigo-700 px-1.5 py-0.5 font-medium">
                    стр. {citation.page_numbers.join(', ')}
                  </span>
                )}
                {citation.extraction_method && (
                  <span className="text-[10px] uppercase tracking-wide text-slate-400">
                    {citation.extraction_method}
                  </span>
                )}
              </div>
              {citation.headings.length > 0 && (
                <div className="text-[11px] text-slate-400 mb-1">
                  {citation.headings.join(' › ')}
                </div>
              )}
              <div>{citation.snippet}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  documentTitle,
  disabled,
  messages,
  isSending,
  onSendMessage,
  onStopGeneration,
}) => {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || disabled || isSending) return
    onSendMessage(input)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto w-full">
      <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-12">
            <div className="w-12 h-12 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-3">
              <Sparkles className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-900">Задайте вопрос по документу</h3>
            <p className="text-sm text-slate-500 max-w-md mt-1">
              ИИ найдет релевантные фрагменты в файле{' '}
              <span className="font-medium text-slate-700">«{documentTitle}»</span> и сформулирует
              точный ответ с цитатами.
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === 'user'
            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center shrink-0 mt-0.5">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-xs ${
                    isUser
                      ? 'bg-indigo-600 text-white rounded-br-sm'
                      : msg.error
                        ? 'bg-rose-50 text-rose-800 border border-rose-200 rounded-bl-sm'
                        : 'bg-white text-slate-800 border border-slate-200 rounded-bl-sm'
                  }`}
                >
                  <div className="whitespace-pre-wrap">
                    {msg.content || (msg.isStreaming ? 'Ищу ответ в документе...' : '')}
                    {msg.isStreaming && (
                      <span className="inline-block w-1.5 h-4 ml-1 align-middle bg-indigo-500 animate-pulse" />
                    )}
                  </div>

                  {!isUser && (msg.citations || msg.sources) && (
                    <SourceAccordion citations={msg.citations ?? []} sources={msg.sources} />
                  )}
                </div>

                {isUser && (
                  <div className="w-8 h-8 rounded-lg bg-slate-200 text-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                    <UserIcon className="w-4 h-4" />
                  </div>
                )}
              </div>
            )
          })
        )}
        <div ref={bottomRef} />
      </div>

      <div className="p-4 bg-white border-t border-slate-200">
        <form onSubmit={handleSubmit} className="flex items-center gap-2 max-w-4xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={disabled || isSending}
            placeholder={
              disabled
                ? 'Дождитесь завершения обработки документа...'
                : 'Спросите что-нибудь о содержании документа...'
            }
            className="flex-1 bg-slate-50 border border-slate-200 focus:border-indigo-500 focus:bg-white focus:outline-none rounded-xl px-4 py-2.5 text-sm transition-colors disabled:opacity-60"
          />

          {isSending ? (
            <button
              type="button"
              onClick={onStopGeneration}
              className="inline-flex items-center gap-1.5 bg-rose-600 hover:bg-rose-700 text-white font-medium px-4 py-2.5 rounded-xl text-sm transition-colors"
            >
              <Square className="w-4 h-4 fill-current" />
              Стоп
            </button>
          ) : (
            <button
              type="submit"
              disabled={disabled || !input.trim()}
              className="inline-flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white font-medium px-4 py-2.5 rounded-xl text-sm transition-colors"
            >
              <Send className="w-4 h-4" />
              Спросить
            </button>
          )}
        </form>
      </div>
    </div>
  )
}
