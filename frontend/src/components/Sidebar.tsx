import React, { useRef } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Clock,
  Trash2,
  Sparkles,
} from 'lucide-react';
import { DocumentItem, DocumentStatus } from '../types';

interface SidebarProps {
  documents: DocumentItem[];
  selectedId: string | null;
  isLoading: boolean;
  isUploading: boolean;
  onSelect: (id: string) => void;
  onUpload: (file: File) => void;
  onDelete: (id: string) => void;
}

const StatusBadge: React.FC<{ status: DocumentStatus }> = ({ status }) => {
  switch (status) {
    case 'completed':
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
          <CheckCircle2 className="w-3 h-3" /> Готов
        </span>
      );
    case 'processing':
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-full">
          <Loader2 className="w-3 h-3 animate-spin" /> Анализ...
        </span>
      );
    case 'pending':
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">
          <Clock className="w-3 h-3" /> В очереди
        </span>
      );
    case 'failed':
      return (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full">
          <AlertCircle className="w-3 h-3" /> Ошибка
        </span>
      );
  }
};

export const Sidebar: React.FC<SidebarProps> = ({
  documents,
  selectedId,
  isLoading,
  isUploading,
  onSelect,
  onUpload,
  onDelete,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onUpload(file);
      e.target.value = '';
    }
  };

  return (
    <aside className="w-full md:w-80 bg-white border-b md:border-b-0 md:border-r border-slate-200 flex flex-col h-auto md:h-screen shrink-0">
      <div className="p-4 border-b border-slate-200 flex items-center gap-2.5">
        <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-sm">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-semibold text-slate-900 leading-tight">AI Конспект</h1>
          <p className="text-xs text-slate-500">Умный анализ и RAG-чат</p>
        </div>
      </div>

      <div className="p-4">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleFileChange}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium py-2.5 px-4 rounded-lg transition-colors shadow-sm text-sm"
        >
          {isUploading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Загрузка файла...
            </>
          ) : (
            <>
              <Upload className="w-4 h-4" />
              Загрузить документ
            </>
          )}
        </button>
        <p className="text-[11px] text-center text-slate-400 mt-1.5">
          Поддерживаются PDF, DOCX, TXT
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-1.5 max-h-60 md:max-h-none">
        <div className="px-2 py-1 text-xs font-semibold uppercase tracking-wider text-slate-400">
          Ваши документы ({documents.length})
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-8 text-slate-400 text-sm gap-2">
            <Loader2 className="w-4 h-4 animate-spin" /> Загрузка...
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-8 px-4 border border-dashed border-slate-200 rounded-lg">
            <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">Документов пока нет</p>
            <p className="text-xs text-slate-400 mt-0.5">
              Загрузите первый файл для конспекта
            </p>
          </div>
        ) : (
          documents.map((doc) => {
            const isSelected = doc.id === selectedId;
            return (
              <div
                key={doc.id}
                onClick={() => onSelect(doc.id)}
                className={`group flex items-start justify-between gap-2 p-3 rounded-lg cursor-pointer transition-all border ${
                  isSelected
                    ? 'bg-indigo-50/70 border-indigo-200 shadow-xs'
                    : 'bg-white border-transparent hover:bg-slate-50 hover:border-slate-200'
                }`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <FileText
                      className={`w-4 h-4 shrink-0 ${
                        isSelected ? 'text-indigo-600' : 'text-slate-400'
                      }`}
                    />
                    <p
                      className={`text-sm font-medium truncate ${
                        isSelected ? 'text-indigo-950' : 'text-slate-800'
                      }`}
                      title={doc.title}
                    >
                      {doc.title}
                    </p>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <StatusBadge status={doc.status} />
                  </div>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(doc.id);
                  }}
                  title="Удалить документ"
                  className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-all"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
