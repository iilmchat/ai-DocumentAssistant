import React, { useState } from 'react';
import { BookOpen, Copy, Check, Loader2, AlertTriangle } from 'lucide-react';
import { DocumentItem } from '../types';

interface SummaryViewerProps {
  document: DocumentItem;
}

export const SummaryViewer: React.FC<SummaryViewerProps> = ({ document }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!document.summary) return;
    navigator.clipboard.writeText(document.summary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (document.status === 'pending' || document.status === 'processing') {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16 px-4 text-center">
        <div className="w-12 h-12 rounded-full bg-indigo-50 flex items-center justify-center mb-4">
          <Loader2 className="w-6 h-6 text-indigo-600 animate-spin" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">
          ИИ изучает ваш документ...
        </h3>
        <p className="text-sm text-slate-500 max-w-md mt-1">
          Мы извлекаем текст, разбиваем его на смысловые фрагменты для поиска и формируем структурированный конспект. Это займет несколько секунд.
        </p>
      </div>
    );
  }

  if (document.status === 'failed') {
    return (
      <div className="flex flex-col items-center justify-center h-full py-16 px-4 text-center">
        <div className="w-12 h-12 rounded-full bg-rose-50 flex items-center justify-center mb-4">
          <AlertTriangle className="w-6 h-6 text-rose-600" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">
          Не удалось обработать документ
        </h3>
        <p className="text-sm text-slate-500 max-w-md mt-1">
          Проверьте корректность файла или настройки OPENAI_API_KEY на сервере.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 bg-slate-50/70 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-800 font-semibold">
            <BookOpen className="w-5 h-5 text-indigo-600" />
            <span>Умный конспект документа</span>
          </div>
          {document.summary && (
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-indigo-600 bg-white border border-slate-200 px-3 py-1.5 rounded-lg transition-colors"
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
          )}
        </div>

        <div className="p-6 text-slate-700 leading-relaxed whitespace-pre-wrap text-sm md:text-base">
          {document.summary || 'Конспект отсутствует.'}
        </div>
      </div>
    </div>
  );
};
